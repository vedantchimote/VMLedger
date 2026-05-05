# VMLedger Documentation

This directory contains the complete documentation for VMLedger, built with [Mintlify](https://mintlify.com).

## Documentation Structure

```
docs/
├── mint.json                 # Mintlify configuration
├── introduction.mdx          # Getting started
├── quickstart.mdx           # 5-minute setup guide
├── installation.mdx         # Detailed installation
├── configuration.mdx        # Configuration guide
├── concepts/                # Core concepts
├── features/                # Feature documentation
├── api-reference/           # API documentation
├── architecture/            # Architecture docs
├── development/             # Development guides
├── deployment/              # Deployment guides
└── guides/                  # How-to guides
```

## Running Documentation Locally

### Prerequisites

- Node.js 18+ installed
- Mintlify CLI installed globally

### Install Mintlify

```bash
npm install -g mintlify
```

### Start Development Server

```bash
cd docs
mintlify dev
```

The documentation will be available at `http://localhost:3000`

## Building Documentation

```bash
mintlify build
```

## Deploying Documentation

### Option 1: Mintlify Cloud (Recommended)

1. Sign up at [mintlify.com](https://mintlify.com)
2. Connect your GitHub repository
3. Mintlify will automatically deploy on push

### Option 2: Self-Hosted

```bash
# Build static site
mintlify build

# Deploy to your hosting provider
# The build output will be in the `_site` directory
```

## Documentation Guidelines

### Writing Style

- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Link to related documentation
- Keep pages focused on one topic

### Code Examples

Always include:
- Multiple language examples (bash, PowerShell, Python, etc.)
- Expected output
- Error handling examples
- Real-world use cases

### Components

Mintlify provides several components:

- `<Card>` - Highlight important content
- `<CardGroup>` - Group related cards
- `<Accordion>` - Collapsible content
- `<Tabs>` - Multiple options
- `<CodeGroup>` - Multiple code examples
- `<Warning>` - Important warnings
- `<Info>` - Helpful information
- `<Check>` - Success messages
- `<Note>` - Additional notes

## Contributing

1. Create a new branch
2. Add/update documentation
3. Test locally with `mintlify dev`
4. Submit a pull request

## Documentation Status

### Completed ✅

- Introduction
- Quick Start
- Installation Guide
- Configuration Guide
- Architecture Overview
- Password Fix Guide

### In Progress 🚧

- API Reference pages
- Feature documentation
- Development guides
- Deployment guides

### Planned 📋

- Video tutorials
- Interactive examples
- Troubleshooting flowcharts
- Performance tuning guide

## Need Help?

- [Mintlify Documentation](https://mintlify.com/docs)
- [VMLedger GitHub](https://github.com/yourusername/vmledger)
- [Report Documentation Issues](https://github.com/yourusername/vmledger/issues)
