from app import app

# Vercel expects the Flask app to be available as a function
def handler(request):
    return app(request.environ, lambda status, headers: None)