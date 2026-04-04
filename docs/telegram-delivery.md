# Telegram delivery (`--delivery`)

When you pass **`--delivery`** on `run`, the pipeline sends the final deliverable from **`runs/book/`** to a Telegram chat after the run completes successfully (after the usual copy into `runs/book/` and the token/cost summary).

## Credentials

Add to **`config/creds.json`** (gitignored):

| Key | Meaning |
|-----|---------|
| `TELEGRAM_BOT_API_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_RECEIVER_ID` | Target chat: numeric user id, group id, or channel `@username` as accepted by the Bot API |

If either value is missing or empty when `--delivery` is set, the run fails with a clear error; details and traceback go to **stderr** and **`run.log`**.

## Which file is sent

The pipeline selects the **newest regular file** in `runs/book/` (by modification time). That should match the file just produced by the book-copy step (MP3/M4A after TTS, PDF after `--no-tts`).

## Bot API methods

- **`.mp3` / `.m4a`** → [`sendAudio`](https://core.telegram.org/bots/api#sendaudio)
- **Other types** (e.g. **`.pdf`**) → [`sendDocument`](https://core.telegram.org/bots/api#senddocument)

## Retries

Transient **network errors** and HTTP **429** / **5xx** responses are retried up to **three** attempts with increasing delay (about 1s, 2s, 4s). Other failures are not retried.
