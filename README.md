# Rental Notifier

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=for-the-badge)](https://github.com/python)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-886FBF?logo=googlegemini&logoColor=white&style=for-the-badge)](https://github.com/google-gemini)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white&style=for-the-badge)](https://github.com/discord)

Scrapes rental listings and sends Discord messages.

**TODO:**
* Implement [![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=github-actions&logoColor=white)](https://docs.github.com/en/actions) for automation.
* Add support for more websites.

| **Status** | **Landlord**                              | **Link**                                                           |
|------------|-------------------------------------------|--------------------------------------------------------------------|
| ⛔         | Mitthem AB                                 | [mitthem.se](https://www.mitthem.se)                              |
| ✅         | Sundsvalls Bostäder                        | [subo.se](https://www.subo.se)                                    |
| ⛔         | Balder                                     | [balder.se](https://www.balder.se)                                |
| ⛔         | Zetterkvist                                | [zetterkvist.com](https://www.zetterkvist.com)                    |
| ✅         | Diös Fastigheter                           | [dios.se](https://www.dios.se)                                    |
| ⛔         | HSB Mitt                                   | [hsb.se](https://www.hsb.se)                                      |
| ⛔         | Sidsjö Fastigheter                         | [sidsjofastigheter.se](https://www.sidsjofastigheter.se)          |
| ⛔         | Tvättbjörnen Förvaltning AB                | [tvattbjornen.se](https://www.tvattbjornen.se)                    |
| ⛔         | KlaraBo                                    | [klarabo.se](https://www.klarabo.se)                              |
| ⛔         | Lilium Fastigheter                         | [liliumab.se](https://www.liliumab.se)                            |
| ⛔         | Hedern Fastigheter AB                      | [hedern.se](https://hedern.se)                                    |
| ⛔         | Neobo Fastigheter AB                       | [neobo.se](https://www.neobo.se)                                  |
| ⛔         | Statera Fastigheter                        | [staterafastigheter.se](https://www.staterafastigheter.se)        |
| ⛔         | Svedin AB                                  | [svedins.se](https://www.svedins.se)                              |
| ⛔         | SveaHem AB                                 | [sveahem.se](https://www.sveahem.se)                              |
| ⛔         | Prima Bostäder Sundsvall AB                | [primabostader.se](https://primabostader.se)                      |
| ⛔         | Sveafastigheter                            | [sveafastigheter.se](https://sveafastigheter.se)                  |


## Command-line Arguments

The following arguments are supported:

```bash
--debug            Run in debug mode
--remove ADDRESS   Address of listing to simulate removal
--recheck          Recheck inactive listings and reactivate if available
--clear            Delete all existing Discord messages
--subo             Run only SUBO scraper
--dios             Run only Dios scraper
```
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