import typing
import binascii
import os

from fastapi import Depends, HTTPException, APIRouter, status, Query, Response, Request
from sqlmodel import Session, select

from db import get_session
from schemas import BlogPostPublicInput, BlogPostInput, BlogPost, NewBlogPost, PageOfResults


router = APIRouter(prefix="/api/blog")

class PlantedBugException(Exception):
    pass


@router.post("/posts", response_model=BlogPostPublicInput, status_code=status.HTTP_201_CREATED)
def create_post(payload: BlogPostPublicInput,
                session: Session = Depends(get_session)) -> BlogPostPublicInput:
    # Generate the checksum
    checksum = binascii.b2a_hex(os.urandom(100))[:5]

    # The first few IDs are reserved
    # This forces an example to be required in order for RESTler to execute the POST successfully
    if payload.id < 10:
        raise HTTPException(status_code=400, detail=f"ID must be at least 10")

    # The payload ID is ignored, and a new one will be assigned
    # (This is intentional to match the behavior of the old demo_server)
    new_blog = NewBlogPost(body=payload.body, checksum=checksum)

    # Add the data to the DB
    new_blog_post = BlogPost.from_orm(new_blog)

    session.add(new_blog_post)
    session.commit()
    session.refresh(new_blog_post)
    return new_blog_post


@router.get("/posts", response_model=PageOfResults, status_code=status.HTTP_200_OK)
def get_posts(page: int = Query(default=10), per_page: int = Query(default=5),
              session: Session = Depends(get_session)) -> PageOfResults:
    if per_page < 2:
        raise HTTPException(status_code=400, detail=f"per_page must be at least 2.")

    query = select(BlogPost).offset(page).limit(per_page)

    items = session.exec(query).all()
    # PLANTED_BUG: unhandled exception when per_page is too high
    # Note: the above query sporadically throws a real exception in this case, so this
    # statement is added for cases when it is not thrown to get consistent test results.
    if per_page > 100000:
        raise HTTPException(status_code=500, detail=f"per_page is too large")

    return PageOfResults(page=page, per_page=per_page, items=items, total=len(items))


@router.put("/posts/{postId}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)  # TODO: all possible statuses in OpenAPI
def update_blog_post(postId: int, payload: BlogPostInput,
                     request: Request,
                     session: Session = Depends(get_session)):
    # PLANTED_BUG to be detected by payload body checker
    def check_no_id_bug():
        # Responds with '500' error if 'id' is missing from the body
        if payload.id is None:
            raise HTTPException(status_code=500, detail=f"ID was not specified.")

    check_no_id_bug()

    # Get the post matching the ID
    blog_post = session.get(BlogPost, postId)
    if blog_post:
        # Confirm the checksum in the BlogPost matches the blog in the database
        # PLANTED BUG 1:
        # This if statement should be confirming that the two checksums match.
        # However, instead raise an exception if they match
        if blog_post.checksum == payload.checksum:
            raise PlantedBugException("Found checksum match")

        blog_post.body = payload.body
        session.commit()
    else:
        raise HTTPException(status_code=404, detail=f"Blog post with id={postId} not found.")


@router.get("/posts/{postId}", response_model=BlogPostPublicInput, status_code=status.HTTP_200_OK)
def get_blog_post(postId: int,
                  session: Session = Depends(get_session)) -> BlogPostInput:
    # Get the post matching the ID
    blog_post = session.get(BlogPost, postId)
    # PLANTED_BUG to be detected by the use after free checker
    # The GET should check if the blog post exists.  Instead, it just returns the blog post found, so
    # a 200 status code is returned with an invalid response body
    # if blog_post:
    #    return blog_post
    # else:
    #    raise HTTPException(status_code=404, detail=f"Blog post with id={postId} not found.")
    return blog_post


@router.delete("/posts/{postId}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_blog_post(postId: int,
                     session: Session = Depends(get_session)):
    blog_post = session.get(BlogPost, postId)  # Note: passing 'id' here generates a 500
    if blog_post:
        session.delete(blog_post)
        session.commit()
    else:
        raise HTTPException(status_code=404, detail=f"Blog post with id={postId} not found.")


