"""Domain layer - the monolith's real boundaries (STACK.md section 2).

    web/  --> domain/  --> models/
    api/  --^

Route handlers parse a request, call ONE function in here, and render.
If a handler is longer than ~25 lines, the logic belongs in this package.
"""
