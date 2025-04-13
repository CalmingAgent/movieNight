# Movie Night Picker App

This is a cross-platform Python application designed to randomly pick movies from a Google Sheets spreadsheet and play their trailers using YouTube. It includes functionality for viewing, reporting, and updating movie trailers, and it works well in WSL, Windows, and macOS environments.

---

## Features

- Randomly selects movies based on the number of attendees.
- Reads movie titles from a Google Spreadsheet.
- Searches for trailers via YouTube Data API and TMDB fallback.
- Creates and launches a YouTube playlist.
- Displays additional visual cues (direction & number images).
- Report incorrect trailers via a GUI-based checkbox interface.
- Automatically updates and populates missing URLs.
- Ignores tabs marked green in Google Sheets.

---

## Requirements

- Python 3.9+
- Google APIs:
  - Google Drive API
  - Google Sheets API
  - YouTube Data API v3
- Dependencies:
  - `google-api-python-client`
  - `google-auth`
  - `google-auth-oauthlib`
  - `python-dotenv`
  - `openpyxl`
  - `Pillow`

## Setup Instructions

1. **Clone the Repository**
```bash
git clone <repo-url>
cd Movie_Night
```

2. **Create and Populate `.env` File**
Create a file named `secret.env`:
```env
SPREADSHEET_ID=your_google_sheet_id
YOUTUBE_API_KEY=your_youtube_api_key
```

3. **Add Google Credentials**
- `service_secret.json`: Google Service Account with access to the spreadsheet.
- `client_secret.json`: OAuth 2.0 credentials (for YouTube playlist creation).

4. **Download the Initial Spreadsheet**
Run:
```bash
python autoUpdate.py
```
This will download the spreadsheet as `ghib.xlsx` and create/update the necessary JSON files.

5. **Run the GUI App**
```bash
python moviePickerApp.py
```

---

## Notes

- **Images** must be located in the `Numbers/` folder using the naming format like:
  - `clockwise.png`
  - `counter_clockwise.png`
  - `number_1.png` ... `number_10.png`

- **Trailer JSON Files** are created in `Video_Trailers/`, one for each non-green sheet.

- **Report Feature**: Use the "Report Trailers" button to flag incorrect trailers. These go into `underReviewURLs.json`.

- Green sheet tabs can be used as notes for the google sheet, it does not get those sheet names

- google sheet format: only uses the first column to get movie names.

- Each sheet name represents typically a genre of such

---

## Troubleshooting

- **Invalid JWT Signature**: Regenerate your `service_secret.json` file from the Google Cloud Console.
- **YouTube Quota Exceeded**: Make sure you aren’t exceeding your API quota. Use `autoUpdate.py` with caution.
- **No Browser in WSL**: Use `wslview` or explicitly open URLs in your Windows default browser.

---

## Credits

Developed by Silent Serenity

---

## License
MIT License

