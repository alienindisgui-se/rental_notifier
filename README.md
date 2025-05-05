# Rental Notifier

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=for-the-badge)](https://github.com/python)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-886FBF?logo=googlegemini&logoColor=white&style=for-the-badge)](https://github.com/google-gemini)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white&style=for-the-badge)](https://github.com/discord)

Scrapes rental listings and sends Discord messages.

**TODO:**
* Implement [![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=github-actions&logoColor=white)](https://docs.github.com/en/actions) for automation.
* Add support for more websites.

## Testing

### Debug Mode
The application supports a debug mode for testing listing removals without scraping the website.

```bash
# Test removal of a specific listing
python main.py --debug --remove "Example Address, 123"
```

#### How it works
- Debug mode loads existing listings from `listings.json`
- The `--remove` flag marks a specified listing as inactive
- This triggers the same notification process as a real removal
- Useful for testing Discord notifications and message updates

**Note:** Make sure you have valid listings in `listings.json` before running debug mode.