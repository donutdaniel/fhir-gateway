# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of FHIR Gateway
- Multi-payer routing for FHIR operations
- OAuth 2.0 with PKCE authentication
- Session-based token management with Redis support
- Token encryption at rest with master key
- Token revocation on logout (RFC 7009)
- MCP (Model Context Protocol) server integration
- Docker and docker-compose support
- Keycloak realm for OAuth testing
- Audit logging for security events
- Rate limiting for API endpoints

### Security
- CSRF protection via state parameter
- Secure session cookies (httponly, secure, samesite)
- Input validation for all endpoints
- Security headers middleware

## [0.1.0] - TBD

- Initial public release
