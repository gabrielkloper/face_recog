from webapp import create_app

app = create_app()

if __name__ == '__main__':
    # Note: For production, use a WSGI server like Gunicorn or Waitress
    # Debug mode should be OFF in production
    app.run(debug=True)
