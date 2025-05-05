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
The application supports a debug mode to test how listings are handled when marked as inactive.

```bash
# Mark a listing as inactive
python main.py --debug --remove "Example Address, 123"

# Run again to see how inactive listings are handled
python main.py
```

#### How it works
- Use `--debug --remove` to mark a listing as inactive in `listings.json`
- Running the script again will:
  - Load all listings including inactive ones
  - Update Discord messages for inactive listings (strikethrough, red color)
  - Keep inactive listings marked as removed
- Useful for testing how the script handles removed listings over multiple runs

**Note:** The script will update existing Discord messages rather than sending new ones for inactive listings.

### Listing States

#### Active (true)
- New listings start as active
- Appears normally in Discord (green color)
- Can be scraped and updated

#### Inactive (false)
Can be triggered in two ways:
1. **Automatic**: Listing disappears from website during scraping
2. **Manual**: Using `--debug --remove` flag

Once inactive:
- Listing stays inactive permanently
- Discord message shows strikethrough and red color
- Won't be reactivated even if found again in scraping
- Useful for manually removing test/duplicate listings