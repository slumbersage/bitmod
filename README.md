
```markdown
BitMod - Your Melodic Companion 🎶💖

Before you embark on the magical journey with BitMod,

follow these steps to set up the enchanting atmosphere:
```
## Prerequisites

Recommended Python version: Python 3.10+

### Install ffmpeg
```bash
sudo apt install ffmpeg
```

### Install openmpt123
```bash
sudo apt install openmpt123
```

### Install Wine and 32-bit architecture
```bash
sudo apt install wine
sudo dpkg --add-architecture i386 && apt-get update &&
apt-get install wine32:i386
```

### Install Python Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

Open the `config.py` file and sprinkle your magic:

- Replace `DISCORD_BOT_TOKEN` with your Discord bot token.
- Replace `MOD_ARCHIVE_API_KEY` with your ModArchive API key.

## Run the Bot

Now, it's time to awaken BitMod:

```bash
python3 bitmod.py
```

And you're done, enjoy!

