# Security Policy

## Supported Versions

This project follows a rolling release model on the main branch. Please apply fixes from the latest version.

## Reporting a Vulnerability

Please do not open public issues for security vulnerabilities.

1. Email the maintainer privately with a clear description and reproduction steps.
2. Include impact assessment and any proof-of-concept details.
3. Allow reasonable time for triage and patching before public disclosure.

## Security Best Practices for Deployments

- Use strong, unique values for JWT_SECRET_KEY and SESSION_SECRET_KEY.
- Set APP_ENV=production in deployed environments.
- Run the app behind HTTPS and a reverse proxy.
- Use PostgreSQL in production instead of SQLite.
- Restrict database credentials and rotate secrets periodically.
- Do not commit .env files or database dumps.
