#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging

from merge_audio import merge_audio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio_to_subtitle import assembly_audio_to_subtitle
from download_youtube import download_youtube
from subtitle_to_speech import process_subtitles
from translate_subtitles import translate_srt_file

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("video_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def process(url):
    video_name = url.split("=")[1]
    
    #第一步：下载视频和音频
    # 使用默认参数下载视频（默认类型为video，质量为best）
    logger.info("第一步，开始下载视频和音频")
    audio_result = download_youtube(url, content_type="audio", audio_format="mp3", audio_quality="0")
    video_result = download_youtube(url, content_type="video", quality="best")

    if video_result.startswith("下载失败") or video_result.startswith("发生错误"):
        logger.error(f"下载视频错误: {video_result}")
        sys.exit(1)
    
    if audio_result.startswith("下载失败") or audio_result.startswith("发生错误"):
        logger.error(f"下载音频错误: {audio_result}")
        sys.exit(1)
    
    logger.info(f"下载成功，视频文件保存在: {video_result}")
    logger.info(f"下载成功，音频文件保存在: {audio_result}")
    
    #第二步：将音频转换为字幕
    # 使用assembly_audio_to_subtitle函数处理音频文件
    logger.info("第二步，开始将音频转换为字幕")
    subtitle_result = assembly_audio_to_subtitle(audio_result)
    
    if subtitle_result.startswith("错误"):
        logger.error(f"音频转字幕错误: {subtitle_result}")
        sys.exit(1)
    
    logger.info(f"字幕文件已保存至: {subtitle_result}")

    #第三步：将字幕转换为汉语字幕
    # 获取输出文件名
    logger.info("第三步，开始将字幕转换为汉语字幕")
    subtitle_name = os.path.basename(subtitle_result)
    name, ext = os.path.splitext(subtitle_name)
    chinese_subtitle = os.path.join(os.path.dirname(subtitle_result), f"{name}_cn{ext}")
    
    # 调用translate_srt_file函数将英文字幕翻译为中文字幕
    max_attempts = 3
    attempt = 0
    translated_subtitle = None
    
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"尝试翻译字幕，第{attempt}次尝试")
        try:
            translated_subtitle = translate_srt_file(subtitle_result, chinese_subtitle)
            if translated_subtitle and os.path.exists(translated_subtitle):
                logger.info(f"翻译成功，第{attempt}次尝试")
                break
            else:
                logger.warning(f"第{attempt}次翻译未生成文件")
        except Exception as e:
            logger.error(f"第{attempt}次翻译出错: {str(e)}")
            if attempt < max_attempts:
                logger.info("准备重试...")
    
    if not translated_subtitle or not os.path.exists(translated_subtitle):
        logger.error("翻译字幕失败，三次尝试后仍未生成翻译文件")
        sys.exit(1)
    
    logger.info(f"中文字幕文件已保存至: {translated_subtitle}")
    
    #第四步：将汉语字幕转换为语音
    # 使用process_subtitles函数处理字幕文件
    logger.info("第四步，开始将汉语字幕转换为语音")
    try:
        generated_audio = process_subtitles(translated_subtitle, video_name, output_dir=f"resources/audios/{video_name}")
        if not os.path.exists(generated_audio):
            logger.error("字幕转语音失败，未生成音频文件")
            sys.exit(1)
        logger.info(f"生成音频文件已保存至: {generated_audio}")
    except Exception as e:
        logger.error(f"字幕转语音过程出错: {str(e)}")
        sys.exit(1)
    
    #第五步：将混合后的音频替换到原始视频中
    logger.info("第五步，开始将混合后的音频替换到原始视频中")
    try:
        print(f"call merge_audio(original_video={video_result}, original_audio={audio_result}, generated_audio={generated_audio}, output_filename=f\"resources/results/{video_name}.mp4\", subtitle_path={translated_subtitle})")
        final_video = merge_audio(original_video=video_result, 
                    original_audio=audio_result, 
                    speaking_audio=generated_audio, 
                    output_filename=f"resources/results/{video_name}.mp4",
                    subtitle_path=translated_subtitle)
        
        if not os.path.exists(final_video):
            logger.error("音视频合并失败，未生成最终视频文件")
            sys.exit(1)
            
        logger.info(f"最终视频文件已保存至: {final_video}")
    except Exception as e:
        logger.error(f"音视频合并过程出错: {str(e)}")
        sys.exit(1)
    
    return final_video

if __name__ == "__main__":
    # 完整流程测试
    try:
        url = "https://www.youtube.com/watch?v=hFZFjoX2cGg&t"
        final_video = process(url)
        logger.info(f"处理完成，最终视频文件已保存至: {final_video}")
    except Exception as e:
        logger.error(f"处理过程中发生未捕获的错误: {str(e)}")
        sys.exit(1)
    