import requests

from typing import List
from termcolor import colored

def search_for_stock_videos(query: str, api_key: str, it: int, min_dur: int) -> List[str]:
    """
    Searches for stock videos based on a query.

    Args:
        query (str): The query to search for.
        api_key (str): The API key to use.

    Returns:
        List[str]: A list of stock videos.
    """
    
    # Build headers
    headers = {
        "Authorization": api_key
    }

    # Build URL
    qurl = f"https://api.pexels.com/videos/search?query={query}&per_page={it}"

    # Send the request
    r = requests.get(qurl, headers=headers)
    
    # Check for API errors first
    if r.status_code == 401:
        print(colored("[-] Pexels API Error: Unauthorized. Check your PEXELS_API_KEY environment variable.", "red"))
        return []
    elif r.status_code != 200:
        print(colored(f"[-] Pexels API Error: HTTP {r.status_code}", "red"))
        return []

    # Parse the response
    response = r.json()
    
    # Check if we have the expected structure
    if "videos" not in response:
        print(colored("[-] Pexels API Error: Unexpected response format", "red"))
        print(colored(f"Response: {response}", "red"))
        return []

    # Parse each video
    raw_urls = []
    video_url = []
    video_res = 0
    try:
        # loop through each video in the result
        for i in range(it):
            # Make sure we have enough videos in the response
            if i >= len(response["videos"]):
                break
            
            #check if video has desired minimum duration
            if response["videos"][i]["duration"] < min_dur:
                continue
            raw_urls = response["videos"][i]["video_files"]
            temp_video_url = ""
            
            # loop through each url to determine the best quality
            for video in raw_urls:
                # Check if video has a valid download link
                if ".com/video-files" in video["link"]:
                    # Only save the URL with the largest resolution
                    if (video["width"]*video["height"]) > video_res:
                        temp_video_url = video["link"]
                        video_res = video["width"]*video["height"]
                        
            # add the url to the return list if it's not empty
            if temp_video_url != "":
                video_url.append(temp_video_url)
                
    except Exception as e:
        print(colored("[-] No Videos found.", "red"))
        print(colored(str(e), "red"))

    # Let user know
    print(colored(f"\t=> \"{query}\" found {len(video_url)} Videos", "cyan"))

    # Return the video url
    return video_url
