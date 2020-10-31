# Guidelines

RESTler is designed to be easy to install and use, and easy to extend to target different types of bugs.

## Design Principles

RESTler is built with these design principles:

- **Keep it simple.** Simple choices are preferred to more complex ones.
The code should be readable, and non-experts in the programming language(s)
should be able to extend it.
- **Minimize dependencies.** Dependencies can be problematic for
long-term compatibility, maintenance, and ease of use. Unless
there is strong justification, we tend to avoid introducing dependencies
to keep things easy to install and more portable.
- **Keep it generic.** RESTler implements heuristics to increase
coverage of the API "out of the box" by analyzing the API specification.
You may find that RESTler cannot support or does not perform well
on your desired API (e.g. it uses a different specification language,
different naming conventions, ...).
We encourage you to open issues and discuss with us,
but will only extend RESTler in a way that applies to a broad set of APIs.
- **Systematic bug hunting over unit testing.** RESTler is designed as a bug finding tool,
 which systematically explores the space of possible request executions of an API
 to find more bugs.  Features to support unit/functional test scenarios for APIs
(e.g. fine-grained control, constraints, serializing test cases) are not the
focus of the tool, and increasing complexity by adding such features should be avoided.

## Support expectations

### Opening Issues

- Don't know whether you're reporting an issue or requesting a feature? File an issue
- Have a question that you don't see answered in docs? File an issue
- Want to know if we're planning on building a particular feature? File an issue
- Got a great idea for a new feature? File an issue
- Found an existing issue that describes yours? Great - up-vote and add additional info / repro steps / etc.

When you hit "New Issue", select the type of issue closest to what you want to report/ask/request.

## Bugs

We aim to respond to bug reports several times a week.
We encourage you to contribute fixes, since we may not be
able to fix all bugs in a timely manner.   For non-trivial fixes,
we would prefer to first discuss the approach for the fix with you before you send a PR.

## Pull Requests

Contributions are welcome!

But first... If you have a question, think you've discovered an issue, would like to propose a new feature, etc., then find/file an issue **BEFORE** starting work to fix/implement it.

### Fork, Clone, Branch and Create your PR

Once you have discussed your proposed feature/fix/etc. with us, and the approach has
been agreed upon, it's time to start development:

1. Fork the repo if you haven't already
2. Clone your fork locally
3. Create & push a feature branch
4. Create a [Draft Pull Request (PR)](https://github.blog/2019-02-14-introducing-draft-pull-requests/)
5. Work on your changes
6. Try to follow the existing style of the related code as closely as possible.

Please see the [pull request template](PullRequestTemplate.md).

When you would like us to review, mark the PR as 'Ready For Review' so that the maintainers can provide feedback.  We will treat community PRs with the same level of scrutiny and rigor as commits submitted by our internal team.

## Testing

For compiler and engine changes, run the existing unit tests,
and add new tests to exercise your new use case.
 These must pass prior to merging your changes.

If you performed targeted testing, we may ask you to check in your artifacts or convert them to automated tests.

For non-trivial changes, please reach out to the maintainers to
discuss your proposed design.   Our unit tests do not cover some
of the more complex functionality, and additional targeted testing will be needed.

