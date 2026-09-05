# %% Packages
import os
import time
import requests

import boto3
from botocore.exceptions import ClientError
import logging

# %% Global Variables
from dotenv import load_dotenv
load_dotenv()

ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
BASE_URL     = "https://graph.threads.net/v1.0"
BUCKET_NAME  = os.environ["BUCKET_NAME"]
PROFILE_NAME = os.environ["PROFILE_NAME"]
AWS_REGION   = os.environ["AWS_REGION"]
MEDIA_DIR    = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# %% Functions
def safe_get(url, params=None):
    """
    A general get function, with safe delay and retry after receiving 429.
    
    Parameters
    ----------
    url: str
        Object url
    
    params: params
        params for requests.get()
            
    Returns
    -------
    response: request.Response object
   
    """
    time.sleep(0.5)
    response = requests.get(url, params=params)

    if response.status_code == 429:
        wait_seconds = int(response.headers.get("Retry-After", 60))
        print(f"被限流了，等待 {wait_seconds} 秒後重試...")
        time.sleep(wait_seconds)
        response = requests.get(url, params=params)

    if not response.ok:
        print("錯誤回應內容：", response.text)

    response.raise_for_status()
    return response


def api_get_json(url, params=None):
    """
    Calling threads api, parsing the response into json.
    
    Parameters
    ----------
    url: str
        Object url
    
    params: params
        params for requests.get()
            
    Returns
    -------
    None (returning json directly)
    
    """
    return safe_get(url, params=params).json()


def fetch_posts_page(url):
    """
    Fetching a post, returning parsed data and next page's url (if exists).
    
    Parameters
    ----------
    url: str
        Object url
    
    Returns
    -------
    None (returning json and url directly)
    
    """
    data     = api_get_json(url)
    next_url = data.get("paging", {}).get("next")
    return data["data"], next_url


def fetch_carousel_children(post_id):
    """
    Fetcning id and downloading url of images/videos in one post.
    
    Parameters
    ----------
    post_id: str
        The id of the post
    
    Returns
    -------
    None (returning children dict directly)
    
    Notes
    -----
    This function is called only if the post contains more than one medium.
    
    """
    url    = f"{BASE_URL}/{post_id}"
    params = {"fields": "children{id, media_type, media_url, thumbnail_url}", "access_token": ACCESS_TOKEN}
    data   = api_get_json(url, params=params)
    return data.get("children", {}).get("data", [])


def fetch_own_replies(post_id, own_username="brownian.motion.99"):
    """
    Recursively fetching replies posted by a specific user below a post.
    
    Parameters
    ----------
    post_id: str
        The id of the post
    
    own_username: str
        Threads username
        
    Returns
    -------
    own_replies: list
        A list of dictionaries containing the replies
    
    """
    url    = f"{BASE_URL}/{post_id}/replies"
    params = {
        "fields": "id, text, timestamp, media_type, username, permalink, is_quote_post",
        "access_token": ACCESS_TOKEN,
    }
    data           = api_get_json(url, params=params)
    direct_replies = data.get("data", [])

    own_replies = []
    for reply in direct_replies:
        if reply.get("username") == own_username:
            own_replies.append(reply)
            own_replies.extend(fetch_own_replies(reply["id"], own_username))

    return own_replies


def download_image(media_id, media_url, media_type):
    """
    Downloading an image/video to local, returning local path of the media.
    
    Parameters
    ----------
    media_id: str
        The id of the image/video
    
    media_url: str
        The url of the image/video
        
    media_type: str
        The type of the medium (VIDEO or OTHERS)
        
    Returns
    -------
    local_path: str
        The local path of the medium
    
    """
    extension = "mp4" if media_type == "VIDEO" else "jpg"
    local_path = os.path.join(MEDIA_DIR, f"{media_id}.{extension}")

    if os.path.exists(local_path):
        return local_path

    response = safe_get(media_url)
    with open(local_path, "wb") as f:
        f.write(response.content)
    return local_path


def upload_image_to_s3(local_path, profile, bucket, region):
    """
    Uploading the medium to the s3 bucket, returning the url.
    
    Parameters
    ----------
    local_path: str
        The local path of the medium
        
    profile: str
        AWS CLI profile
    
    bucket: str
        AWS S3 bucket name
    
    Returns
    -------
    url: str
        The AWS url of the object
    
    """
    object_name = local_path.rpartition("/")[-1]
    
    session = boto3.Session(profile_name = profile)
    client  = session.client("s3")
    try:
        response = client.upload_file(local_path, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return None
    
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{object_name}"
    return url

# %% Testing
if __name__ == "__main__":
    url = upload_image_to_s3("ingestion/test.jpg", PROFILE_NAME, BUCKET_NAME, AWS_REGION)
    print(url)