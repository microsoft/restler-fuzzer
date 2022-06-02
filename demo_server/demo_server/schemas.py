import json

from sqlmodel import SQLModel, Field
from typing import Optional, List


class BlogPostPublicInput(SQLModel):
    id: int
    body: str

    class Config:
        schema_extra = {
            "example": {
                "id": 99,
                "body": "my first blog post"
            }
        }


class BlogPostInput(SQLModel):
    id: int = Field(default=None)  # make 'id' optional here for planted bug
    body: str
    # TODO: diagnose payload body checker issue. it cannot find this bug if checksum is required.
    # Then, remove this (it should be required)
    checksum: str = Field(default=None)

    class Config:
        schema_extra = {
            "example": {
                "id": 22,
                "body": "my first blog post",
                "checksum": "abcde"
            }
        }


class NewBlogPost(SQLModel):
    body: str
    checksum: str


class BlogPost(BlogPostInput, table=True):
    id: int = Field(default=None, primary_key=True)


class PageOfResults(SQLModel):
    items: List[BlogPostInput]
    per_page: int
    page: int
    total: int
