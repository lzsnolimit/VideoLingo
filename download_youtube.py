import os
import subprocess
import time
import re
from pathlib import Path

def extract_video_id(url):
    """从YouTube URL中提取视频ID"""
    # 尝试匹配常见的YouTube URL格式
    pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def download_youtube(url, content_type="video", quality="best", audio_format="mp3", audio_quality="0"):
    """
    使用yt-dlp下载YouTube视频或音频到指定目录，使用视频ID或时间戳作为文件名
    
    参数:
        url (str): YouTube视频URL
        content_type (str): 内容类型，'video'或'audio'
        quality (str): 视频质量，默认为'best'，可选值如:
                      - 'best': 最佳视频和音频质量
                      - '1080p': 1080p视频
                      - '720p': 720p视频
        audio_format (str): 音频格式，默认'mp3'，可选'm4a'、'wav'、'opus'等
        audio_quality (str): 音频质量，0(最好)到9(最差)，默认为0
    
    返回:
        str: 成功时返回下载文件的相对路径，失败时返回错误信息
    """
    
    # 尝试提取视频ID，如果失败则使用时间戳
    video_id = extract_video_id(url)
    if not video_id:
        video_id = str(int(time.time()))
    
    # 构建命令
    command = ["yt-dlp"]
    
    if content_type == "video":
        # 构建视频格式参数
        if quality == "best":
            format_arg = "bestvideo+bestaudio/best"
        elif quality == "1080p":
            format_arg = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif quality == "720p":
            format_arg = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        else:
            format_arg = quality
        
        command.extend([
            "-f", format_arg,
            "--merge-output-format", "mp4"
        ])
        output_dir = "resources/videos"
        file_path = f"{output_dir}/{video_id}.mp4"
        output_template = file_path
    
    else:  # 音频下载
        command.extend([
            "-x",  # 提取音频
            "--audio-format", audio_format,
            "--audio-quality", audio_quality
        ])
        output_dir = "resources/audios"
        file_path = f"{output_dir}/{video_id}.{audio_format}"
        output_template = file_path
    
    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 添加输出模板
    command.extend(["-o", output_template])
    
    # 添加URL
    command.append(url)
    
    try:
        # 执行下载命令
        result = subprocess.run(
            command, 
            check=True,
            capture_output=True,
            text=True
        )
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            return file_path
        
        # 如果找不到预期的文件，尝试从输出中提取
        print("can't find the file{}".format(file_path))
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines:
            if "Destination" in line and ":" in line:
                return line.split(":", 1)[1].strip()
            elif "[Merger] Merging formats into" in line:
                return line.replace("[Merger] Merging formats into ", "").replace('"', '').strip()
        
        # 如果仍然找不到，返回可能的路径
        return file_path
    
    except subprocess.CalledProcessError as e:
        return f"下载失败: {e.stderr}"
    
    except Exception as e:
        return f"发生错误: {str(e)}"

# 使用示例
if __name__ == "__main__":
    video_url = "https://www.youtube.com/watch?v=A_5Nd3vAG9k"
    
    # 下载音频
    audio_result = download_youtube(video_url, content_type="audio", audio_format="mp3")
    print(audio_result)
    
    # 下载视频
    video_result = download_youtube(video_url, content_type="video")
    print(video_result)
    


    