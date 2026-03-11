from app.api.router import handle_request


def handler(event, context):
    return handle_request(event or {})
