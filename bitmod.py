import discord
from discord.ext import commands, tasks
from discord.utils import *
import subprocess
import asyncio
import os
from modarchive_api import *
from discord import *
import config
from collections import deque
import requests
from typing import Callable, Optional
import xml.etree as ET
import io
from io import BytesIO
import random
import re

api_key = config.MOD_ARCHIVE_API_KEY

queue = deque()

queued_module_ids = set()

skip_votes = {}

stop_votes = {}

rskip_votes = {}

voice_channel_timers = {}


currently_playing = False

# Creating an instance of Intents with all flags enabled
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


# Event triggered when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    check_voice_channel_members.start()  # Start the check_voice_channel_members loop when the bot is ready



@bot.event
async def on_play(ctx, mod_info, duration):
    global voice_channel_timers

    # Update the bot's presence with the current song title
    if not mod_info:
        return

    # Get the song title from the mod_info
    song_title = mod_info.get('songtitle', 'Unknown Song')

    # Convert duration from seconds to minutes and seconds
    minutes = int(duration // 60)
    seconds = int(duration % 60)

    # Change the bot's presence before joining the voice channel
    await bot.change_presence(activity=discord.Game(name=f"🎵 {song_title} | ⏳ {minutes}m : {seconds}s"), status=discord.Status.dnd)

    # Reset the timer
    guild_id = ctx.guild.id
    if guild_id in voice_channel_timers:
        voice_channel_timers.pop(guild_id)


bot.remove_command('help')


# Define a custom help command
@bot.command()
async def help(ctx):
    # Load the thumbnail image file
    thumbnail_path = "icon.jpg"  # Replace with the actual path to your image file

    embed = discord.Embed(title="Available Commands", color=0xFF69B4)

    # Add the image as the thumbnail
    with open(thumbnail_path, "rb") as thumbnail_file:
        embed.set_thumbnail(url="attachment://thumbnail.jpg")
        thumbnail = discord.File(thumbnail_file, filename="thumbnail.jpg")

    # Add custom help content
    embed.add_field(name="!rplay", value="Play random module files continuously.", inline=False)
    embed.add_field(name="!loop <mod_file_id>", value="Play a specific module file in a loop.", inline=False)
    embed.add_field(name="!rskip", value="Skip the current song in the rplay loop.", inline=False)
    embed.add_field(name="!play <mod_file_id>", value="Play a specific module file.", inline=False)
    embed.add_field(name="!skip", value="Skip the current module.", inline=False)
    embed.add_field(name="!stop", value="Stop playback and clear the queue.", inline=False)
    embed.add_field(name="!list", value="Show the current queue.", inline=False)
    embed.add_field(name="!random [format] [genre] [channels] [size]", value="Play a random module based on optional parameters.", inline=False)
    embed.add_field(name="!search <query>", value="Search for modules with embedded pagination.", inline=False)
    embed.add_field(name="!formats", value="Display available module formats.", inline=False)
    embed.add_field(name="!genres", value="Display available genres.", inline=False)
    embed.add_field(name="!mp3 <mod_file_id>", value="Download modules as MP3 files.", inline=False)
        # Add the footer
    embed.set_footer(text="Made with ❤️ by Altin and Aiko.\nSpecial thanks to The Mod Archive team.", icon_url="https://imgur.com/LWonquS.jpeg")
    embed.set_author(name="BitMod's Lovely Bot Help ", icon_url="https://i.imgur.com/qTYuE1M.png")

    await ctx.send(embed=embed, file=thumbnail)


@bot.command()
async def formats(ctx):
    # Load the thumbnail image file for the !formats command
    thumbnail_path = "icon.jpg"  # Replace with the actual path to your image file

    embed = discord.Embed(title="Available Module Formats", color=0x3498db)

    # Add the image as the thumbnail
    with open(thumbnail_path, "rb") as thumbnail_file:
        embed.set_thumbnail(url="attachment://formats_thumbnail.jpg")
        thumbnail = discord.File(thumbnail_file, filename="formats_thumbnail.jpg")

    # Available module formats
    formats_list = "669, AHX, HVL, IT, MED, MO3, MOD, MTM, S3M, STM, XM, OCT, OKT, DMF, MPTM, ULT, FAR, MDL, AMS, AMF, PTM, PSM, MT2, DBM, DIGI, IMF, J2B, PLM, GDM, DSM, UMX, SFX, STP, DTM, C67"

    # Add the list of formats to the embed
    embed.add_field(name="Supported Formats", value=formats_list, inline=False)
    embed.set_footer(text="Made with ❤️ by Altin and Aiko.\nSpecial thanks to The Mod Archive team.", icon_url="https://imgur.com/LWonquS.jpeg")
    await ctx.send(embed=embed, file=thumbnail)



# Command to run openmpt123 with specific options
openmpt123_command = ['openmpt123', '--render', '--filter', '1']

# Function to download a module file from ModArchive using the API
def download_mod_file(module_id):
    mod_info_xml = get_module_by_id(api_key, module_id, include_comments=True, include_reviews=True)

    if mod_info_xml is None:
        print(f"Error retrieving module information for ID {module_id}.")
        return None, None

    try:
        mod_info = parse_module_info(mod_info_xml)
    except ET.ParseError as e:
        print(f"Error parsing XML for ID {module_id}: {e}")
        return None, None

    if mod_info is None:
        print(f"Error parsing module information from XML for ID {module_id}.")
        return None, None

    mod_url = mod_info.get('url')
    if not mod_url:
        print(f"Error: Module URL not found for ID {module_id}.")
        return None, None

    response = requests.get(mod_url)

    if response.status_code != 200:
        print(f"Error downloading MOD file for ID {module_id}: {response.status_code}")
        return None, None

    return response.content, mod_info

# Function to convert a module file to WAV using openmpt123


def convert_mod_to_wav(mod_content, file_name, original_file_extension):
    # Check if the files already exist and delete them
    wav_file_path = f"{file_name}.{original_file_extension}.wav"
    mod_file_path = f"{file_name}.{original_file_extension}"

    if os.path.exists(wav_file_path):
        os.remove(wav_file_path)

    if os.path.exists(mod_file_path):
        os.remove(mod_file_path)

    # Write the module content to the file with the correct extension
    with open(f"{file_name}.{original_file_extension}", "wb") as mod_file:
        mod_file.write(mod_content)

    # Determine the conversion command based on the file extension
    if original_file_extension.lower() == 'mod':
        command = ['openmpt123', '--render', '--filter', '1', f"{file_name}.{original_file_extension}"]
    elif original_file_extension.lower() in ['hvl', 'ahx']:
        command = ['wine', 'hvl2wav.exe', f"{file_name}.{original_file_extension}"]
    else:
        command = ['openmpt123', '--render', f"{file_name}.{original_file_extension}"]

    # Run the conversion process
    conversion_process = subprocess.Popen(
        command,
        stderr=subprocess.PIPE
    )

    # Wait for the conversion process to complete
    _, error_output = conversion_process.communicate()
    if conversion_process.returncode != 0:
        print("Error during conversion:", error_output.decode())
        return None

    # Check if the file was converted using HVL2WAV and rename it accordingly
    if original_file_extension.lower() in ['hvl', 'ahx']:
        os.rename(f"{file_name}.wav", f"{file_name}.{original_file_extension}.wav")

    return f"{file_name}.{original_file_extension}.wav"

# Function to play a WAV file in a voice channel
async def play_wav_in_voice_channel(ctx, wav_file):
    # Check if the author is in a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        return

    # Connect to the voice channel
    voice_channel = await ctx.author.voice.channel.connect()

    # Custom class for FFmpegPCMAudio
    class MyAudio(discord.FFmpegPCMAudio):
        def __init__(self, source, *args, **kwargs):
            super().__init__(source, *args, **kwargs)

        def read(self):
            ret = super().read()
            if ret is None:
                self.cleanup()
            return ret

    # Play the audio in the voice channel
    voice_channel.play(MyAudio(executable="ffmpeg", source=wav_file))

    # Wait for the playback to complete
    while voice_channel.is_playing():
        await asyncio.sleep(1)

    # Disconnect from the voice channel
    await voice_channel.disconnect()



# Create a task to periodically check voice channel members
@tasks.loop(seconds=20)
async def check_voice_channel_members():
    global currently_playing, stop_votes

    for guild in bot.guilds:
        for voice_channel in guild.voice_channels:
            if bot.user in voice_channel.members:
                # If there are other members, reset the timer
                if len(voice_channel.members) > 1:
                    if guild.id in voice_channel_timers:
                        voice_channel_timers.pop(guild.id)
                # If the bot is the only member, start or reset the timer
                else:
                    if guild.id not in voice_channel_timers:
                        voice_channel_timers[guild.id] = 0
                    voice_channel_timers[guild.id] += 5  # Increase timer by 5 seconds

                    # If the timer reaches 30 seconds, stop playback, clear queue, and disconnect
                    if voice_channel_timers[guild.id] >= 30:
                        if guild.voice_client:  # Check if the bot is connected to a voice channel
                            await guild.voice_client.disconnect()
                        if currently_playing:
                            currently_playing = False
                            queue.clear()
                            stop_votes.clear()
                            await bot.change_presence(activity=None, status=discord.Status.idle)



# Modified stop command to handle errors and check if the bot is the only member in the voice channel
@bot.command()
async def stop(ctx):
    global currently_playing, stop_votes

    # Check if the user is connected to a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        embed = discord.Embed(
            title="**Not Connected to Voice Channel!**",
            description="You need to be in a voice channel to stop **music**.",
            color=0xFF0000
        )
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return

    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    # Check if something is currently playing
    if voice_channel and voice_channel.is_playing():
        # Check if the user has already voted
        if ctx.author.id in stop_votes:
            await ctx.send("You've already voted to stop playback.")
        else:
            # Add the user to the list of votes
            stop_votes[ctx.author.id] = True

            # Calculate the number of votes needed to stop
            votes_needed = len(ctx.author.voice.channel.members) // 2

            # Check if enough votes have been received
            if len(stop_votes) >= votes_needed:
                await ctx.send("Stopping playback and clearing the queue.")
                currently_playing = False
                queue.clear()
                stop_votes.clear()  # Clear the votes after stopping
                if voice_channel:
                    voice_channel.stop()
                    await voice_channel.disconnect()
                # set the bot presence to idle    
                await bot.change_presence(activity=None, status=discord.Status.idle)

                    
            else:
                await ctx.send(f"Vote recorded! {votes_needed - len(stop_votes)} more votes needed to stop playback.")
    else:
        await ctx.send("Nothing is currently playing.")
        
        

#  You can reset the votes manually with another command if needed
# @bot.command()
# async def reset_stop_votes(ctx):
#     global stop_votes
#     stop_votes = {}
#     await ctx.send("Stop votes reset.")





# Command to reset the timer when someone joins or leaves the voice channel
@bot.event
async def on_voice_state_update(member, before, after):
    global voice_channel_timers

    if bot.user.id == member.id:
        # Bot's own voice state update, reset the timer
        if after.channel:
            guild_id = after.channel.guild.id
            if guild_id in voice_channel_timers:
                voice_channel_timers.pop(guild_id)


# Ensure the loop is stopped when the bot is closed
@bot.event
async def on_disconnect():
    check_voice_channel_members.stop()



@bot.command()
async def rplay(ctx, format=None, genre=None):
    global currently_playing

    

    # Check if the user is connected to a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        embed = discord.Embed(title="**Not Connected to Voice Channel!**", description="You need to be in a voice channel to play **music**.", color=0xFF0000)
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    
    # If something is already playing, add to the queue
    if currently_playing:
        await ctx.send("Already playing a module. Please wait for the current one to finish.")
        return

    # Set the flag to indicate that something is now playing
    currently_playing = True

    while currently_playing:
        # Get a random module ID based on the specified format
        random_mod_id = get_random_module_id(api_key, format=format, genre=genre)

        # Download the module file and retrieve information
        mod_content, mod_info = download_mod_file(random_mod_id)
        if not mod_content or not mod_info:
            continue  # Skip to the next iteration if download fails

        # Get the original file extension from the API response
        original_file_extension = mod_info.get('format', 'mod').lower()

        # Convert the module file to WAV using openmpt123 or HVL2WAV
        wav_file = convert_mod_to_wav(mod_content, str(random_mod_id), original_file_extension)
        if not wav_file:
            continue  # Skip to the next iteration if conversion fails
        
        duration = get_wav_duration(wav_file)
        await on_play(ctx, mod_info, duration)
        
        # Generate the module info image with specified positions
        background_image, img_path, mod_info = generate_module_info_image_with_custom_background(api_key,
            random_mod_id, "np.jpg", {"id": (90, 340), "filename": (90, 240), 'date': (90, 135), 'size': (641, 312), 'hits': (90, 190), 'songtitle': (90, 290)}
        )

        # Send the image as an embed with the module link
        module_link = f"https://modarchive.org/index.php?request=view_by_moduleid&query={random_mod_id}"
        embed = discord.Embed(color=0x72638B)
        file = discord.File(img_path, filename="module_info.png")
        embed.set_image(url="attachment://module_info.png")
        embed.description = f"[View on Archive]({module_link})"
        message = await ctx.send(embed=embed, file=file)

        # React with a series of emojis to indicate repeat
        repeat_emojis = ["🔃"]
        for emoji in repeat_emojis:
            await message.add_reaction(emoji)

        # Play the WAV file in the voice channel
        await play_wav_in_voice_channel(ctx, wav_file)

        # Remove the temporary files
        os.remove(f"{str(random_mod_id)}.{original_file_extension}")
        os.remove(f"{str(random_mod_id)}.{original_file_extension}.wav")
        os.remove(img_path)  # Remove the image file from your system

    # Reset the flag to indicate that playback is complete
    currently_playing = False

# Function to play a module file in a loop
@bot.command()
async def loop(ctx, mod_file_id):
    global currently_playing

    # Check if the user is connected to a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        # Send an embed message with the icon for not being in a voice channel
        embed = discord.Embed(title="**Not Connected to Voice Channel!**", description="You need to be in a voice channel to play **music**.", color=0xFF0000)
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    
    # Check if the provided argument is a valid number
    if not mod_file_id.isdigit():
        # Send an embed message with the icon for invalid input
        embed = discord.Embed(title="**Invalid Input!**", description="Please provide a valid numeric module ID.", color=0xFF0000)
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    
    

    # If something is already playing, add to the queue
    if currently_playing:
        if mod_file_id in queue:
            await ctx.send(f"Module with ID {mod_file_id} is already in the queue.")
            return

        queue.append(mod_file_id)
        await ctx.send("Module added to the loop queue. It will play repeatedly until skipped or stopped.")
        return

    # Set the flag to indicate that something is now playing
    currently_playing = True

    # Download the module file and retrieve information
    mod_content, mod_info = download_mod_file(mod_file_id)
    if not mod_content or not mod_info:
        currently_playing = False  # Reset the flag if download fails
        embed = discord.Embed(
            title="**Error!**",
            description="Error retrieving module information. Please try again.",
            color=0xFF0000
        )
        embed.set_thumbnail(url="attachment://icon.jpg")
        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return

    # Get the original file extension from the API response
    original_file_extension = mod_info.get('format', 'mod').lower()

    # Convert the module file to WAV using openmpt123 or HVL2WAV
    wav_file = convert_mod_to_wav(mod_content, str(mod_file_id), original_file_extension)
    if not wav_file:
        currently_playing = False  # Reset the flag if conversion fails
        return
    duration = get_wav_duration(wav_file)
    
    await on_play(ctx, mod_info, duration)
    

    # Generate the module info image with specified positions
    background_image, img_path, mod_info = generate_module_info_image_with_custom_background(api_key,
        mod_file_id, "np.jpg", {"id": (90, 340), "filename": (90, 240), 'date': (90, 135), 'size': (641, 312), 'hits': (90, 190), 'songtitle': (90, 290)}
    )

    # Send the image as an embed with the module link
    module_link = f"https://modarchive.org/index.php?request=view_by_moduleid&query={mod_file_id}"
    embed = discord.Embed(color=0x72638B)
    file = discord.File(img_path, filename="module_info.png")
    embed.set_image(url="attachment://module_info.png")
    embed.description = f"[View on Archive]({module_link})"
    message = await ctx.send(embed=embed, file=file)

    # React with a series of emojis to indicate repeat
    repeat_emojis = ["🔂"]
    for emoji in repeat_emojis:
        await message.add_reaction(emoji)

    # Play the WAV file in the voice channel in a loop
    while currently_playing:
        await play_wav_in_voice_channel(ctx, wav_file)

    # Remove the temporary files
    os.remove(f"{str(mod_file_id)}.{original_file_extension}")
    os.remove(f"{str(mod_file_id)}.{original_file_extension}.wav")
    os.remove(img_path)  # Remove the image file from your system

    # Reset the flag to indicate that playback is complete
    currently_playing = False

    # Check the queue for more modules
    if queue:
        next_module_id = queue.popleft()
        await loop(ctx, next_module_id)  # Recursive call to loop the next module





@bot.command()
async def rskip(ctx):
    global currently_playing, rskip_votes

    # Check if the user is connected to a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        # Send an embed message with the icon for not being in a voice channel
        embed = discord.Embed(
            title="**Not Connected to Voice Channel!**",
            description="You need to be in a voice channel to skip **music**.",
            color=0xFF0000
        )
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)


    # Check if something is currently playing
    if not currently_playing:
        await ctx.send("Nothing is currently playing.")
        return

    # Check if the user has already voted
    if ctx.author.id in rskip_votes:
        await ctx.send("You've already voted to skip the current song in the loop.")
    else:
        # Add the user to the list of votes
        rskip_votes[ctx.author.id] = True

        # Calculate the number of votes needed to skip
        votes_needed = len(ctx.author.voice.channel.members) // 2

        # Check if enough votes have been received
        if len(rskip_votes) >= votes_needed:
            await ctx.send("Skipping the current song in the loop.")
            voice_channel.stop()
            rskip_votes.clear()  # Clear the votes after skipping
            await bot.change_presence(activity=None, status=discord.Status.online)
        else:
            await ctx.send(f"Vote recorded! {votes_needed - len(rskip_votes)} more votes needed to skip the current song in the loop.")


def get_wav_duration(file_path):
    try:
        # Run ffmpeg command to get duration
        result = subprocess.run(['ffmpeg', '-i', file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Extract duration from ffmpeg output
        duration_match = re.search(r'Duration: (\d{2}:\d{2}:\d{2}\.\d+)', result.stderr)
        if duration_match:
            duration_str = duration_match.group(1)
            hours, minutes, seconds = map(float, duration_str.split(':'))
            duration_in_seconds = hours * 3600 + minutes * 60 + seconds
            return duration_in_seconds
        else:
            print("Error extracting duration from ffmpeg output.")
            return None
    except Exception as e:
        print(f"Error getting duration: {e}")
        return None

# Command to play a module file
@bot.command()
async def play(ctx, mod_file_id):
    global currently_playing

    # Check if the provided argument is a valid number
    if not mod_file_id.isdigit():
        # Send an embed message with the icon for invalid input
        embed = discord.Embed(title="**Invalid Input!**", description="Please provide a valid numeric module ID.", color=0xFF0000)
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    
        # Check if the user is connected to a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        # Send an embed message with the icon for not being in a voice channel
        embed = discord.Embed(title="**Not Connected to Voice Channel!**", description="You need to be in a voice channel to play **music**.", color=0xFF0000)
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    
    if ctx.message.content.startswith('!loop'):
        await loop(ctx, mod_file_id)
        return


    # If something is already playing, add to the queue
    if currently_playing:
        if mod_file_id in queue:
            await ctx.send(f"Module with ID {mod_file_id} is already in the queue.")
            return

        queue.append(mod_file_id)
        await ctx.send("Module added to the queue. Please wait for your turn!")
        return

    # Set the flag to indicate that something is now playing
    currently_playing = True





    # Download the module file and retrieve information
    mod_content, mod_info = download_mod_file(mod_file_id)
    if not mod_content or not mod_info:
        currently_playing = False  # Reset the flag if download fails
        embed = discord.Embed(
            title="**Error!**",
            description="Error retrieving module information. Please try again.",
            color=0xFF0000
        )
        embed.set_thumbnail(url="attachment://icon.jpg")
        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return
    # Get the original file extension from the API response
    original_file_extension = mod_info.get('format', 'mod').lower()
    
    
    


    # Convert the module file to WAV using openmpt123 or HVL2WAV
    wav_file = convert_mod_to_wav(mod_content, str(mod_file_id), original_file_extension)
    if not wav_file:
        currently_playing = False  # Reset the flag if conversion fails
        return
    duration = get_wav_duration(wav_file)
    
    await on_play(ctx, mod_info, duration)
    

    # Generate the module info image with specified positions
    background_image, img_path, mod_info = generate_module_info_image_with_custom_background(api_key,
        mod_file_id, "np.jpg", {"id": (90, 340), "filename": (90, 240), 'date': (90, 135), 'size': (641, 312), 'hits': (90, 190), 'songtitle': (90, 290)}
    )

    # Send the image as an embed


    # Send the image as an embed with the module link
      # Send the image as an embed with the module link below
    module_link = f"https://modarchive.org/index.php?request=view_by_moduleid&query={mod_file_id}"
    embed = discord.Embed(color=0x72638B)
    file = discord.File(img_path, filename="module_info.png")
    embed.set_image(url="attachment://module_info.png")
    embed.description = f"[View on Archive]({module_link})"
    await ctx.send(embed=embed, file=file)


    # Play the WAV file in the voice channel
    await play_wav_in_voice_channel(ctx, wav_file)

    # Remove the temporary files
    os.remove(f"{str(mod_file_id)}.{original_file_extension}")
    os.remove(f"{str(mod_file_id)}.{original_file_extension}.wav")
    os.remove(img_path)  # Remove the image file from your system

    # Reset the flag to indicate that playback is complete
    currently_playing = False
    await bot.change_presence(activity=None, status=discord.Status.online)
    # Check the queue for more modules
    if queue:
        next_module_id = queue.popleft()
        await play(ctx, next_module_id)  # Recursive call to play the next module


    



@bot.command()
async def skip(ctx):
    global currently_playing, skip_votes

    # Check if the user is connected to a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        # Send an embed message with the icon for not being in a voice channel
        embed = discord.Embed(
            title="**Not Connected to Voice Channel!**",
            description="You need to be in a voice channel to skip **music**.",
            color=0xFF0000
        )
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return

    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    # Check if something is currently playing
    if voice_channel and voice_channel.is_playing():
        # Check if the user has already voted
        if ctx.author.id in skip_votes:
            await ctx.send("You've already voted to skip.")
        else:
            # Add the user to the list of votes
            skip_votes[ctx.author.id] = True

            # Calculate the number of votes needed to skip
            votes_needed = len(ctx.author.voice.channel.members) // 2

            # Check if enough votes have been received
            if len(skip_votes) >= votes_needed:
                await ctx.send("Skipping the current module.")
                voice_channel.stop()
                skip_votes.clear()  # Clear the votes after skipping
                
                await bot.change_presence(activity=None, status=discord.Status.online)

            else:
                await ctx.send(f"Vote recorded! {votes_needed - len(skip_votes)} more votes needed to skip.")
    else:
        await ctx.send("Nothing is currently playing.")


#  You can reset the votes manually with another command if needed
# @bot.command()
# async def reset_votes(ctx):
#     global skip_votes
#     skip_votes = {}
#     await ctx.send("Votes reset.")






@bot.command()
async def list(ctx):
    if not queue:
        await ctx.send("The queue is currently empty.")
        return

    queue_list = "\n".join(f"{index + 1}. {mod_id}" for index, mod_id in enumerate(queue))
    await ctx.send(f"Current Queue:\n{queue_list}")


# Function to play a random module

@bot.command()
async def random(ctx, format='*', genre='*', channels='*', size='*'):
    if format == '*':
        format = None
    if genre == '*':
        genre = None
    if channels == '*':
        channels = None
    if size == '*':
        size = None

    random_mod_id = get_random_module_id(api_key, format=format, genre=genre, size=size, channels=channels)

    if random_mod_id:
        await play(ctx, random_mod_id)
    else:
        await ctx.send("Error getting a random module.")


# Command to search for modules with embedded pagination
@bot.command()
async def search(ctx, *args):
    query = " ".join(args)

    # Search for modules using the provided query
    xml_content = search_modules(api_key, 'filename', query)
    
    if xml_content is None:
        await ctx.send("Error searching for modules.")
        return

    # Parse the search results
    search_results = parse_search_results(xml_content)

    if not search_results:
        await ctx.send("No modules found for the given query.")
        return

    # Format and send the search results as embedded messages with pagination
    formatted_results = format_search_results(search_results)
    pages = [formatted_results[i:i+2] for i in range(0, len(formatted_results), 2)]

    current_page = 0
    embed_message = await ctx.send(embed=create_embed(current_page + 1, len(pages), pages[current_page]))




    # Add reactions for pagination
    await embed_message.add_reaction("⬅️")
    await embed_message.add_reaction("➡️")

    # Define a check function to ensure the reactions are from the command author
    def check(reaction, user):
        return user == ctx.author and reaction.message.id == embed_message.id

    while True:
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
        except TimeoutError:
            break

        if reaction.emoji == "⬅️" and current_page > 0:
            current_page -= 1
        elif reaction.emoji == "➡️" and current_page < len(pages) - 1:
            current_page += 1
        else:
            continue

        await embed_message.edit(embed=create_embed(current_page + 1, len(pages), pages[current_page]))
        await embed_message.remove_reaction(reaction.emoji, ctx.author)


# Helper function to create an embed
def create_embed(current_page, total_pages, page_results):
    embed = discord.Embed(color=0x00ff00)
    embed.title = f"Search Results (Page {current_page}/{total_pages})"
    
    # Add fields horizontally
    for i, result in enumerate(page_results, start=1):
        embed.add_field(name=f"Result {i}", value=result, inline=True)

    return embed





@bot.command()
async def genres(ctx):
    api_key = config.MOD_ARCHIVE_API_KEY
    genre_xml = get_genre_list(api_key)

    if not genre_xml:
        await ctx.send("Error retrieving genre list.")
        return

    parsed_genres = parse_genre_xml(genre_xml)

    if not parsed_genres:
        await ctx.send("Error parsing genre list.")
        return

    # Format and send the genres as an embedded message
    formatted_genres = format_genre_list(parsed_genres)
    pages = [formatted_genres[i:i+15] for i in range(0, len(formatted_genres), 15)]  # Display 15 genres per page

    current_page = 0
    embed_message = await ctx.send(embed=create_genre_embed(current_page + 1, len(pages), pages[current_page]))

    # Add reactions for pagination
    await embed_message.add_reaction("⬅️")
    await embed_message.add_reaction("➡️")

    # Define a check function to ensure the reactions are from the command author
    def check(reaction, user):
        return user == ctx.author and reaction.message.id == embed_message.id

    while True:
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
        except TimeoutError:
            break

        if reaction.emoji == "⬅️" and current_page > 0:
            current_page -= 1
        elif reaction.emoji == "➡️" and current_page < len(pages) - 1:
            current_page += 1
        else:
            continue

        await embed_message.edit(embed=create_genre_embed(current_page + 1, len(pages), pages[current_page]))
        await embed_message.remove_reaction(reaction.emoji, ctx.author)




def create_genre_embed(current_page, total_pages, page_genres):
    embed = discord.Embed(color=0x00ff00)
    embed.title = f"Available Genres (Page {current_page}/{total_pages})"
    
    # Add fields horizontally
    for i, genre in enumerate(page_genres, start=1):
        embed.add_field(name=f"Genre {i}", value=genre, inline=True)

    return embed

# Helper function to format the genre list
def format_genre_list(genres):
    formatted_genres = []
    for genre in genres:
        formatted_genres.append(f"{genre['name']} (ID: {genre['id']}, Files: {genre['files']})")
        if 'children' in genre:
            for child_genre in genre['children']:
                formatted_genres.append(f"  - {child_genre['name']} (ID: {child_genre['id']}, Files: {child_genre['files']})")
    
    return formatted_genres



# Function to convert a WAV file to MP3 using FFmpeg
def convert_wav_to_mp3(wav_file, mp3_file):
    try:
        subprocess.run(['ffmpeg', '-i', wav_file, '-codec:a', 'libmp3lame', mp3_file])
    except Exception as e:
        print(f"Error converting {wav_file} to {mp3_file} using FFmpeg: {e}")

# Function to clean up temporary files
def cleanup_temp_files(*files):
    for file in files:
        try:
            os.remove(file)
        except Exception as e:
            print(f"Error deleting {file}: {e}")






@bot.command()
async def mp3(ctx, mod_file_id):
    # Check if the provided argument is a valid number
    if not mod_file_id.isdigit():
        # Send an embed message with the icon for invalid input
        embed = discord.Embed(title="**Invalid Input!**", description="Please provide a valid numeric module ID.", color=0xFF0000)
        embed.set_thumbnail(url="attachment://icon.jpg")

        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return

    # Download the module file and retrieve information
    mod_content, mod_info = download_mod_file(mod_file_id)
    if not mod_content or not mod_info:
        embed = discord.Embed(
            title="**Error!**",
            description="Error retrieving module information. Please try again.",
            color=0xFF0000
        )
        embed.set_thumbnail(url="attachment://icon.jpg")
        with open("icon.jpg", "rb") as icon_file:
            icon = discord.File(icon_file, filename="icon.jpg")
            await ctx.send(embed=embed, file=icon)
        return

    # Get the original file extension from the API response
    original_file_extension = mod_info.get('format', 'mod').lower()

    # Convert the module file to WAV using openmpt123 or HVL2WAV
    wav_file = convert_mod_to_wav(mod_content, str(mod_file_id), original_file_extension)
    if not wav_file:
        return



    # Send a loading gif while waiting for the file to be converted
    loading_message = await ctx.send("Converting your melody... 🔄")

    # Convert the WAV file to MP3 using FFmpeg
    mp3_file = f"{mod_info['songtitle']}.mp3"
    convert_wav_to_mp3(wav_file, mp3_file)


    # Create an embed with the File.io link and a loading message
    embed = discord.Embed(
            title="🎶 Melodious Creation Ready!",
            description=f"Hey {ctx.author.mention}, your enchanting melody is now ready ❤️",
            color=0x00FF00  # You can choose a color for the embed
        )
    embed.set_author(name="BitMod", icon_url="https://i1.sndcdn.com/artworks-Z5LJGyo5okuuxQcg-zGDzqA-t500x500.jpg")  # Add your bot's name and icon

        # Add additional fields to the embed if needed
    embed.add_field(name="Song Title", value=mod_info['songtitle'], inline=True)
    embed.add_field(name="Date Released", value=mod_info['date'], inline=True)
        # Include a link to the MP3 file on File.io
        # embed.add_field(name="Download Your Melody", value=f"[{mod_info['songtitle']}.mp3]({file_link})")
    embed.add_field(name="Uploading File...", value=f"Sending MP3 file directly...")

    message = await ctx.send(embed=embed)

    # Send the MP3 file as an attachment in the same message
    await ctx.send(file=discord.File(mp3_file), reference=message)

        
        
    cleanup_temp_files(wav_file, mp3_file, f"{str(mod_file_id)}.{original_file_extension}")


bot.run(config.DISCORD_BOT_TOKEN)


