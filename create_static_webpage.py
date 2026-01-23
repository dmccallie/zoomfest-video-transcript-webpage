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

    /* Active transcript segment (synced with video) */
    .speakertext.active {{
      background-color: rgba(74, 144, 226, 0.3);
      border-left: 3px solid #4a90e2;
      padding-left: 8px;
      margin-left: -11px;
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
    #autoscroll-toggle {{
      padding: 8px 16px;
      background-color: #2d5;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
    }}
    #autoscroll-toggle:hover {{
      background-color: #2a4;
    }}
    #autoscroll-toggle.disabled {{
      background-color: #666;
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
    
    /* Video error message */
    #video-error {{
      display: none;
      background-color: rgba(255, 100, 100, 0.2);
      border: 2px solid #ff6666;
      border-radius: 8px;
      padding: 20px;
      margin: 20px;
      color: #ffcccc;
    }}
    #video-error h3 {{
      margin-top: 0;
      color: #ff9999;
    }}

  </style>
</head>
<body>
  <div class="container">
    <!-- Video container -->
    <div id="video-container">
      <video id="zoomVideo" controls playsinline preload="metadata">
        <source src="{video_url}" type="video/mp4; codecs=hvc1" />
        <source src="{video_url}" type="video/mp4" />
        <source src="{video_url}" />
        Your browser does not support the video tag or this video format.
      </video>
      <div id="video-error">
        <h3>⚠️ Video Loading Error</h3>
        <p><strong>The video failed to load or play.</strong></p>
        <p>On iOS/Safari, this is often caused by H.265/HEVC encoding, which has limited browser support.</p>
        <p><strong>Solution:</strong> Re-encode the video to H.264 format using:</p>
        <code style="display: block; background: #000; padding: 10px; margin: 10px 0; border-radius: 4px;">
          ffmpeg -i input.mp4 -c:v libx264 -preset slow -crf 23 -c:a aac output.mp4
        </code>
        <p style="font-size: 0.9em; margin-top: 15px;">H.264 is universally supported across all browsers and devices.</p>
      </div>
    </div>

    <!-- Draggable separator -->
    <div id="separator"></div>

    <!-- Search box -->
    <div id="search-container">
      <input type="text" id="search-input" placeholder="Search transcript..." />
      <button class="search-button" id="prev-button" disabled>Previous</button>
      <button class="search-button" id="next-button" disabled>Next</button>
      <span id="search-info"></span>
      <button id="autoscroll-toggle" class="enabled">Auto-Scroll: ON</button>
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

    // Video error handling and debugging
    const video = document.getElementById('zoomVideo');
    const videoError = document.getElementById('video-error');
    
    video.addEventListener('error', function(e) {{
      console.error('Video error:', e);
      if (video.error) {{
        console.error('Error code:', video.error.code);
        console.error('Error message:', video.error.message);
        // Show friendly error message
        videoError.style.display = 'block';
      }}
    }});
    
    video.addEventListener('loadstart', function() {{
      console.log('Video loading started');
      videoError.style.display = 'none';
    }});
    
    video.addEventListener('canplay', function() {{
      console.log('Video can play');
      videoError.style.display = 'none';
    }});
    
    video.addEventListener('loadedmetadata', function() {{
      console.log('Video metadata loaded');
    }});

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

    // Auto-scroll functionality
    let autoScrollEnabled = true;
    let currentActiveElement = null;
    let userIsScrolling = false;
    let scrollTimeout = null;
    const autoscrollToggle = document.getElementById('autoscroll-toggle');
    const transcriptContainer = document.getElementById('transcript-container');

    // Toggle auto-scroll on/off
    autoscrollToggle.addEventListener('click', () => {{
      autoScrollEnabled = !autoScrollEnabled;
      if (autoScrollEnabled) {{
        autoscrollToggle.textContent = 'Auto-Scroll: ON';
        autoscrollToggle.classList.remove('disabled');
        autoscrollToggle.classList.add('enabled');
      }} else {{
        autoscrollToggle.textContent = 'Auto-Scroll: OFF';
        autoscrollToggle.classList.remove('enabled');
        autoscrollToggle.classList.add('disabled');
      }}
    }});

    // Detect when user manually scrolls
    transcriptContainer.addEventListener('scroll', () => {{
      if (autoScrollEnabled) {{
        userIsScrolling = true;
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {{
          userIsScrolling = false;
        }}, 2000); // Re-enable auto-scroll after 2 seconds of no scrolling
      }}
    }});

    // Sync transcript with video playback
    video.addEventListener('timeupdate', () => {{
      if (!autoScrollEnabled || userIsScrolling) return;
      
      const currentTime = video.currentTime;
      const allTextElements = transcriptContainer.querySelectorAll('.speakertext');
      
      // Find the current active segment
      let activeElement = null;
      for (let i = allTextElements.length - 1; i >= 0; i--) {{
        const elementTime = parseFloat(allTextElements[i].getAttribute('data-time'));
        if (currentTime >= elementTime) {{
          activeElement = allTextElements[i];
          break;
        }}
      }}
      
      // Update highlighting if active element changed
      if (activeElement && activeElement !== currentActiveElement) {{
        if (currentActiveElement) {{
          currentActiveElement.classList.remove('active');
        }}
        activeElement.classList.add('active');
        currentActiveElement = activeElement;
        
        // Scroll to keep active element visible
        activeElement.scrollIntoView({{
          behavior: 'smooth',
          block: 'center'
        }});
      }}
    }});

    // Clear active highlight when video is paused or seeking
    video.addEventListener('pause', () => {{
      if (currentActiveElement) {{
        currentActiveElement.classList.remove('active');
        currentActiveElement = null;
      }}
    }});

    video.addEventListener('seeking', () => {{
      userIsScrolling = false; // Allow auto-scroll after manual seek
    }});

    // Draggable separator functionality
    const separator = document.getElementById('separator');
    const videoContainer = document.getElementById('video-container');
    const container = document.querySelector('.container');

    let isDragging = false;

    function startDrag(e) {{
      isDragging = true;
      // Capture pointer for all pointer types (mouse, touch, pen)
      if (e.pointerId !== undefined) {{
        separator.setPointerCapture(e.pointerId);
      }}
      e.preventDefault();
      e.stopPropagation();
    }}

    function onDrag(e) {{
      if (!isDragging) return;
      
      let clientY;
      // Handle both pointer and touch events
      if (e.clientY !== undefined) {{
        clientY = e.clientY;
      }} else if (e.touches && e.touches.length > 0) {{
        clientY = e.touches[0].clientY;
      }} else {{
        return;
      }}
      
      const containerTop = container.getBoundingClientRect().top;
      let newHeight = clientY - containerTop;
      const minHeight = 100;
      const maxHeight = window.innerHeight - 100;
      newHeight = Math.max(minHeight, Math.min(maxHeight, newHeight));
      videoContainer.style.height = newHeight + 'px';
      e.preventDefault();
      e.stopPropagation();
    }}

    function endDrag(e) {{
      if (!isDragging) return;
      isDragging = false;
      if (e.pointerId !== undefined) {{
        separator.releasePointerCapture(e.pointerId);
      }}
      e.preventDefault();
      e.stopPropagation();
    }}

    // Use pointer events (handles mouse, touch, and pen)
    separator.addEventListener('pointerdown', startDrag);
    separator.addEventListener('pointermove', onDrag);
    separator.addEventListener('pointerup', endDrag);
    separator.addEventListener('pointercancel', endDrag);
    
    // Global handlers for when pointer moves outside separator
    window.addEventListener('pointermove', onDrag);
    window.addEventListener('pointerup', endDrag);

        
    // for timestamp clicks and touches
    let touchStartY = 0;
    let touchStartX = 0;
    const scrollThreshold = 10; // pixels of movement to consider it a scroll
    
    function handleTouchStart(e) {{
        touchStartY = e.touches[0].clientY;
        touchStartX = e.touches[0].clientX;
    }}
    
    function handleTouchEnd(e) {{
        const touchEndY = e.changedTouches[0].clientY;
        const touchEndX = e.changedTouches[0].clientX;
        const deltaY = Math.abs(touchEndY - touchStartY);
        const deltaX = Math.abs(touchEndX - touchStartX);
        
        // Only trigger if it's a tap (minimal movement), not a scroll
        if (deltaY < scrollThreshold && deltaX < scrollThreshold) {{
            e.preventDefault();
            const time = parseFloat(this.getAttribute('data-time'));
            const video = document.getElementById('zoomVideo');
            video.currentTime = time;
            
            // play() returns a promise, handle it properly for iOS
            const playPromise = video.play();
            if (playPromise !== undefined) {{
              playPromise.catch(error => {{
                // Auto-play was prevented, user needs to click play button
                console.log('Playback prevented:', error);
              }});
            }}
        }}
    }}
    
    function handleClick(e) {{
        const time = parseFloat(this.getAttribute('data-time'));
        const video = document.getElementById('zoomVideo');
        video.currentTime = time;
        
        // play() returns a promise, handle it properly for iOS
        const playPromise = video.play();
        if (playPromise !== undefined) {{
          playPromise.catch(error => {{
            // Auto-play was prevented
            console.log('Playback prevented:', error);
          }});
        }}
    }}

    document.querySelectorAll('.timestamp, .speakername, .speakertext').forEach(function(element) {{
        element.addEventListener('click', handleClick);
        element.addEventListener('touchstart', handleTouchStart, {{ passive: true }});
        element.addEventListener('touchend', handleTouchEnd);
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
