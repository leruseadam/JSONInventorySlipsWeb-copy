# Inventory Slip Generator

A Flask web application for generating inventory slips from CSV and JSON data with support for Bamboo and Cultivera formats.

## Features

- Import data from CSV files
- Import data from JSON URLs (Bamboo, Cultivera, GrowFlow)
- Generate Word documents with inventory slips
- Support for multiple data formats
- Modern web interface

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python app.py`

## Usage

1. Start the application
2. Import data via CSV upload, JSON URL, or paste JSON data
3. Review the data in the data view
4. Select items and generate inventory slips
5. Download the generated Word document

## Troubleshooting

### Chrome Authentication Issues

If the app doesn't work when you're signed into Google Chrome, try these solutions:

1. **Use Incognito Mode**: Press `Ctrl+Shift+N` (Windows/Linux) or `Cmd+Shift+N` (Mac) and navigate to the app URL
2. **Clear Browser Data**: Clear cache and cookies for localhost
3. **Disable Extensions**: Temporarily disable Chrome extensions
4. **Use Different Browser**: Try Firefox or Safari
5. **Test Compatibility**: Use the "Test Chrome Compatibility" button on the home page

### Common Issues

- **Session Storage**: The app uses chunked session storage to handle large datasets
- **File Downloads**: Generated files are saved to your Downloads folder
- **Port Conflicts**: The app will automatically try different ports if the default is in use

## Development

The app includes several improvements for Chrome compatibility:

- Security headers configured for local development
- Session cookies set to 'Lax' SameSite policy
- CORS headers for localhost
- Chrome-specific browser flags for authentication issues
- Session debugging tools

## License

See LICENSE file for details.