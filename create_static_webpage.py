#!/usr/bin/env python3

# parses the VTT file and generates an HTML page with a video player
# and a scrollable transcript area below it. Each transcript cue is clickable
# to seek to the corresponding time in the video.

# you should have uploaded your video to a public S3 bucket or similar
# so it can be accessed via a URL.

# then take the output HTML file and open it in a web browser.
# then copy to an S3 bucket or similar for sharing.

# example usage:
# python create_static_webpage.py --video_url \
#   https://mccallie-family-stories.s3.us-east-1.amazonaws.com/zoomvideos/Zoomfest-JBM-SJM-KPM-18Jan2026.mp4 \
#   "/mnt/d/Dropbox/McCallieFamilyStories/Zoomfest-18Jan2026/GMT20260118-190759_Recording.transcript.vtt" \
#   test.html

import re
import argparse

def parse_timestamp(timestamp):
    """
    Convert a VTT timestamp (HH:MM:SS.mmm) into seconds (float).
    Example: "00:22:10.660" => 1330.66 seconds.
    Can also parse seconds --> seconds if not in HH:MM:SS format.
    """
    parts = timestamp.split(':')
    if len(parts) == 1:
        # assume it's just seconds
        return float(parts[0])
    
    if len(parts) == 3:
        # assume it's HH:MM:SS format
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")

def fix_spelling(text):
    """ fix a few family name transcription errors """
    corrections = [
      ("McCauley", "McCallie"),
      ("Catherine", "Katharine"),
      ("Chicago coal", "Chicago cold"),
      ("HIROX", "High Rocks")
    ]
    for wrong, right in corrections:
        text = text.replace(wrong, right)

    return text

def parse_vtt_file(vtt_filename):
    """
    Parse a VTT file and extract cues as a list of tuples:
    (start_time_in_seconds, text)
    This function ignores cue numbers and only uses the start time.
    """
    cues = []
    with open(vtt_filename, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Skip header lines or empty lines
        if line == "" or line.startswith("WEBVTT"):
            i += 1
            continue

        # If the line is just a number, it's likely a cue identifier; skip it.
        if re.match(r'^\d+$', line):
            i += 1
            continue

        # Look for the timestamp line (contains '-->')
        if '-->' in line:
            # Example line: "00:22:10.660 --> 00:22:17.119"
            parts = line.split('-->')
            start_timestamp = parts[0].strip()
            try:
                start_time = parse_timestamp(start_timestamp)
            except ValueError as e:
                print(f"Warning: {e}. Skipping cue.")
                i += 1
                continue

            # The cue text is on the following lines until an empty line is encountered.
            # strip the speaker off the first line if present (e.g., "Speaker 1: Hello world")
            i += 1
            text_lines = []
            speaker = ""
            while i < len(lines) and lines[i].strip() != "":
                speaker_split = lines[i].strip().split(":", 1)
                if len(speaker_split) == 2:
                    speaker = speaker_split[0].strip()
                    fixed_text = fix_spelling(speaker_split[1].strip())
                    text_lines.append(fixed_text)
                else: 
                  raw_text = lines[i].strip()
                  fixed_text = fix_spelling(raw_text)
                  text_lines.append(fixed_text)
                i += 1
            cue_text = " ".join(text_lines)
            cues.append((speaker, start_time, cue_text))
        else:
            i += 1

    return cues

def format_time(seconds):
    """
    Format seconds (float) into HH:MM:SS (if hours > 0) or MM:SS string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    else:
        return f"{minutes:02}:{secs:02}"

def generate_html(cues, video_url):
    """
    Generate a full HTML page as a string. The page uses a flex container with
    a video element at the top and a scrollable transcript area below.
    Each transcript cue is clickable to seek to the start time.
    """
    transcript_lines = ""

    # group speakers into paragraphs, with header for each speaker and starting timestamp
    # then add each cue as a paragraph with clickable timestamp
    # break to new speaker when transcript indicates a new speaker

    last_speaker = None

    for speaker, start_time, text in cues:
        formatted_time = format_time(start_time)
        # do we have a new speaker?
        if speaker != last_speaker:
            if last_speaker is not None:
                # close previous speaker's paragraph
                transcript_lines += f'      </div>\n'
            # start new speaker section
            transcript_lines += f'      <div class="speaker-section">\n'
            transcript_lines += f'        <span class=speakername data-time="{start_time}">{speaker}</span> <span class="timestamp" data-time="{start_time}">[ {formatted_time} ]</span>\n'
            last_speaker = speaker
          
        transcript_lines += f'        <p>\n'
        transcript_lines += f'          <span class=speakertext data-time="{start_time}">{text}</span>\n'
        transcript_lines += f'        </p>\n'

    if last_speaker is not None:
        # close the last speaker's section
        transcript_lines += f'      </div>\n'

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Zoom Call Transcript with Flex Layout</title>
  <style>
    /* Ensure the page uses full viewport height and removes default margins */
    html, body {{
      height: 100%;
      margin: 0;
      font-family: Georgia, serif;
      background-color: #01182c;
      color: #ded9d9;
      line-height: 1.4;
    }}
    /* The main flex container fills the viewport */
    .container {{
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}
    /* Video container (its height is adjustable via JavaScript) */
    #video-container {{
      padding: 10px;
      height: 50vh;
      overflow: hidden;
    }}
    #video-container video {{
      width: 100%;
      height: 100%;
      object-fit: contain;
    }}

    /* Separator bar: draggable by the user */
    #separator {{
        position: relative;
        height: 5px;
        background: #ccc;
        cursor: ns-resize; /* use ns-resize for vertical dragging */
        touch-action: none;
        -webkit-user-select: none;
        user-select: none;
    }}
    
    /* Create a larger invisible hit area for iOS iPad */
    #separator::before {{
        content: "";
        position: absolute;
        top: -10px;
        bottom: -10px;
        left: 0;
        right: 0;
    }}

    /* Search box styling */
    #search-container {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 20px;
      background-color: rgba(255, 255, 255, 0.05);
      border-top: 1px solid #ccc;
      border-bottom: 1px solid #ccc;
      flex-wrap: wrap;
    }}

    /* Transcript container takes remaining space and scrolls if needed */
    #transcript-container {{
      flex: 1;
      overflow-y: auto;
      padding: 30px;
      display: flex;
      justify-content: center;
    }}
    .transcript {{
      max-width: 1000px;
      width: 100%;
    }}
    .transcript p {{
      margin-bottom: 15px;
    }}
    .timestamp {{
      position: relative;
      color: white;
      cursor: pointer;
    }}
    /* make expanded hit area for timestamp clicks and touches */
    .timestamp::before {{
      content: "";
      position: absolute;
      top: -15px;
      left: -15px;
      right: -15px;
      bottom: -15px;
    }}
    .speakername {{
      font-weight: bold;
      font-size: 1.15em;
      margin-right: 10px;
      cursor: pointer;
    }}
    /* inset speaker text to distinguish from speaker name */
    .speakertext {{
      font-size: 1.1em;
      cursor: pointer;
    }}
    .speaker-section {{
      margin-bottom: 25px;
      padding: 15px;
      border-radius: 10px;
    }}
    .speaker-section:nth-child(odd) {{
      background-color: rgba(255, 255, 255, 0.03);
    }}
    .speaker-section:nth-child(even) {{
      background-color: rgba(255, 255, 255, 0.06);
    }}
    .speaker-section p {{
      margin-top: 5px;
      margin-bottom: 10px;
      margin-left: 20px;
    }}

    #search-input {{
      flex: 1;
      min-width: 200px;
      padding: 8px 12px;
      border: 1px solid #555;
      border-radius: 4px;
      background-color: #002244;
      color: white;
      font-size: 16px;
    }}
    #search-input:focus {{
      outline: none;
      border-color: #4a90e2;
    }}
    .search-button {{
      padding: 8px 16px;
      background-color: #4a90e2;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
    }}
    .search-button:hover {{
      background-color: #357abd;
    }}
    .search-button:disabled {{
      background-color: #555;
      cursor: not-allowed;
    }}
    #search-info {{
      color: #aaa;
      font-size: 14px;
      min-width: 120px;
    }}
    /* Highlight styles */
    .search-highlight {{
      background-color: yellow;
      color: black;
      padding: 2px 0;
    }}
    .search-highlight.current {{
      background-color: orange;
      color: black;
    }}

  </style>
</head>
<body>
  <div class="container">
    <!-- Video container -->
    <div id="video-container">
      <video id="zoomVideo" controls>
        <source src="{video_url}" type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>

    <!-- Draggable separator -->
    <div id="separator"></div>

    <!-- Search box -->
    <div id="search-container">
      <input type="text" id="search-input" placeholder="Search transcript..." />
      <button class="search-button" id="prev-button" disabled>Previous</button>
      <button class="search-button" id="next-button" disabled>Next</button>
      <span id="search-info"></span>
    </div>

    <!-- Transcript container -->
    <div id="transcript-container">
      <div class="transcript">
{transcript_lines}
      </div>
    </div>
  </div>

  <!-- JavaScript to enable clickable transcript timestamps -->
  <script>

    // Search functionality
    let searchMatches = [];
    let currentMatchIndex = -1;
    const searchInput = document.getElementById('search-input');
    const prevButton = document.getElementById('prev-button');
    const nextButton = document.getElementById('next-button');
    const searchInfo = document.getElementById('search-info');
    const transcriptDiv = document.querySelector('.transcript');

    function clearHighlights() {{
      const highlights = transcriptDiv.querySelectorAll('.search-highlight');
      highlights.forEach(highlight => {{
        const parent = highlight.parentNode;
        parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
        parent.normalize();
      }});
      searchMatches = [];
      currentMatchIndex = -1;
    }}

    function highlightMatches(searchTerm) {{
      if (!searchTerm || searchTerm.length < 2) {{
        clearHighlights();
        searchInfo.textContent = '';
        prevButton.disabled = true;
        nextButton.disabled = true;
        return;
      }}

      clearHighlights();
      const speakerTextElements = transcriptDiv.querySelectorAll('.speakertext');
      const searchRegex = new RegExp(searchTerm.replace(/[.*+?^${{}}()|[\\\\]\\\\\\\\]/g, '\\\\$&'), 'gi');

      speakerTextElements.forEach(element => {{
        const originalText = element.textContent;
        const matches = [...originalText.matchAll(searchRegex)];
        
        if (matches.length > 0) {{
          let lastIndex = 0;
          const fragment = document.createDocumentFragment();
          
          matches.forEach(match => {{
            // Add text before match
            if (match.index > lastIndex) {{
              fragment.appendChild(document.createTextNode(originalText.substring(lastIndex, match.index)));
            }}
            // Add highlighted match
            const mark = document.createElement('span');
            mark.className = 'search-highlight';
            mark.textContent = match[0];
            fragment.appendChild(mark);
            searchMatches.push(mark);
            lastIndex = match.index + match[0].length;
          }});
          
          // Add remaining text
          if (lastIndex < originalText.length) {{
            fragment.appendChild(document.createTextNode(originalText.substring(lastIndex)));
          }}
          
          element.textContent = '';
          element.appendChild(fragment);
        }}
      }});

      if (searchMatches.length > 0) {{
        currentMatchIndex = 0;
        updateCurrentMatch();
        prevButton.disabled = false;
        nextButton.disabled = false;
      }} else {{
        searchInfo.textContent = 'No matches';
        prevButton.disabled = true;
        nextButton.disabled = true;
      }}
    }}

    function updateCurrentMatch() {{
      searchMatches.forEach((match, index) => {{
        if (index === currentMatchIndex) {{
          match.classList.add('current');
          match.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        }} else {{
          match.classList.remove('current');
        }}
      }});
      searchInfo.textContent = `${{currentMatchIndex + 1}} of ${{searchMatches.length}}`;
    }}

    searchInput.addEventListener('input', (e) => {{
      highlightMatches(e.target.value);
    }});

    searchInput.addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') {{
        if (e.shiftKey) {{
          prevMatch();
        }} else {{
          nextMatch();
        }}
      }}
    }});

    function nextMatch() {{
      if (searchMatches.length > 0) {{
        currentMatchIndex = (currentMatchIndex + 1) % searchMatches.length;
        updateCurrentMatch();
      }}
    }}

    function prevMatch() {{
      if (searchMatches.length > 0) {{
        currentMatchIndex = (currentMatchIndex - 1 + searchMatches.length) % searchMatches.length;
        updateCurrentMatch();
      }}
    }}

    nextButton.addEventListener('click', nextMatch);
    prevButton.addEventListener('click', prevMatch);

    // Draggable separator functionality
    const separator = document.getElementById('separator');
    const videoContainer = document.getElementById('video-container');
    const container = document.querySelector('.container');

    let isDragging = false;

    // Unified handler for starting a drag.
    function startDrag(e) {{
      isDragging = true;
      // If pointer events are supported, capture the pointer.
      if (e.pointerId) {{
        separator.setPointerCapture(e.pointerId);
      }}
      e.preventDefault();
    }}

    // Unified handler for moving during a drag.
    function onDrag(e) {{
      if (!isDragging) return;
      let clientY;
      if (e.clientY !== undefined) {{
        clientY = e.clientY;
      }} else if (e.touches && e.touches.length > 0) {{
        clientY = e.touches[0].clientY;
      }} else {{
        return;
      }}
      let containerTop = container.getBoundingClientRect().top;
      let newHeight = clientY - containerTop;
      const minHeight = 100;
      const maxHeight = window.innerHeight - 100;
      newHeight = Math.max(minHeight, Math.min(maxHeight, newHeight));
      videoContainer.style.height = newHeight + 'px';
      e.preventDefault();
    }}

    // Unified handler for ending a drag.
    function endDrag(e) {{
      isDragging = false;
      if (e.pointerId) {{
        separator.releasePointerCapture(e.pointerId);
      }}
      e.preventDefault();
    }}

    // Pointer events (for most desktop and modern browsers)
    separator.addEventListener('pointerdown', startDrag);
    window.addEventListener('pointermove', onDrag);
    window.addEventListener('pointerup', endDrag);

    // Touch events as a fallback (make sure to set passive: false)
    separator.addEventListener('touchstart', startDrag, {{ passive: false }});
    window.addEventListener('touchmove', onDrag, {{ passive: false }});
    window.addEventListener('touchend', endDrag, {{ passive: false }});

        
    // for timestamp clicks and touches
    function handleTimestampEvent(e) {{
        // Prevent any default touch behavior
        e.preventDefault();
        const time = parseFloat(this.getAttribute('data-time'));
        const video = document.getElementById('zoomVideo');
        video.currentTime = time;
        video.play();
    }}

    document.querySelectorAll('.timestamp, .speakername, .speakertext').forEach(function(element) {{
        element.addEventListener('click', handleTimestampEvent);
        // Adding touchstart ensures immediate response on touch devices.
        element.addEventListener('touchstart', handleTimestampEvent, {{ passive: false }});
    }});

  </script>
</body>
</html>
'''
    return html_content

def main():
    parser = argparse.ArgumentParser(description="Generate an HTML transcript page from a VTT file.")
    parser.add_argument("vtt_file", help="Path to the VTT file")
    parser.add_argument("output_file", help="Output HTML file path")
    parser.add_argument("--video_url", 
                        default="https://your-bucket.mp4",
                        help="URL of the video file")
    args = parser.parse_args()

    cues = parse_vtt_file(args.vtt_file)
    if not cues:
        print("No cues found in the VTT file. Exiting.")
        return

    html = generate_html(cues, args.video_url)

    with open(args.output_file, 'w', encoding='utf-8') as out:
        out.write(html)
    print(f"HTML file generated: {args.output_file}")

if __name__ == "__main__":
    main()
