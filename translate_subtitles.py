#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import json
import logging
from typing import List, Dict, Tuple
from openai import OpenAI

def setup_logger(log_file=None, log_level=logging.INFO):
    """
    设置日志记录器
    
    Args:
        log_file: 日志文件路径，如不提供则只输出到控制台
        log_level: 日志级别
        
    Returns:
        配置好的logger对象
    """
    # 创建logger
    logger = logging.getLogger('subtitle_translator')
    logger.setLevel(log_level)
    
    # 定义日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果提供了日志文件路径，创建文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# 创建全局logger
logger = logging.getLogger('subtitle_translator')

def parse_srt(file_path: str) -> List[Dict]:
    """
    解析SRT字幕文件
    
    Args:
        file_path: SRT文件路径
        
    Returns:
        解析后的字幕列表，每项包含序号、时间码和文本
    """
    logger.info(f"开始解析SRT文件: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 将内容按字幕块分割
        subtitle_blocks = re.split(r'\n\n+', content.strip())
        logger.debug(f"分割出 {len(subtitle_blocks)} 个字幕块")
        
        subtitles = []
        
        for i, block in enumerate(subtitle_blocks):
            lines = block.strip().split('\n')
            if len(lines) >= 3:  # 确保至少有序号、时间码和一行文本
                subtitle_id = lines[0]
                timecode = lines[1]
                text = '\n'.join(lines[2:])  # 文本可能有多行
                
                subtitles.append({
                    'id': subtitle_id,
                    'timecode': timecode,
                    'text': text
                })
            else:
                logger.warning(f"字幕块 #{i+1} 格式不正确，已跳过: {block}")
        
        logger.info(f"成功解析 {len(subtitles)} 条字幕")
        return subtitles
    except Exception as e:
        logger.error(f"解析SRT文件失败: {e}", exc_info=True)
        raise

def analyze_subtitle_content(texts: List[str]) -> str:
    """
    分析字幕内容，获取主题和上下文
    
    Args:
        texts: 字幕文本列表
        
    Returns:
        分析结果
    """
    logger.info("开始分析字幕内容")
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("缺少API密钥，请设置DEEPSEEK_API_KEY环境变量")
        raise ValueError("缺少API密钥，请设置DEEPSEEK_API_KEY环境变量")
    
    # 创建OpenAI客户端
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    # 取样分析，如果字幕太多，只分析部分
    sample_size = min(50, len(texts))
    step = max(1, len(texts) // sample_size)
    sample_texts = [texts[i] for i in range(0, len(texts), step)][:sample_size]
    
    logger.debug(f"从 {len(texts)} 条字幕中取样 {len(sample_texts)} 条进行分析")
    
    combined_text = "\n\n".join(sample_texts)
    
    prompt = f"""请分析以下视频字幕内容，提取主要信息：

1. 视频主题和类型
2. 主要内容概述
3. 专业术语或特殊词汇
4. 语言风格和语调

请简洁地返回分析结果，以便能更好地进行字幕翻译。

字幕内容：
{combined_text}"""
    
    try:
        logger.debug("发送API请求进行内容分析")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位专业的视频内容分析师，擅长理解和总结视频内容。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=8192,
            stream=False
        )
        
        analysis = response.choices[0].message.content
        logger.info("内容分析完成")
        logger.debug(f"分析结果:\n{analysis}")
        return analysis
    
    except Exception as e:
        logger.error(f"分析字幕内容时出错: {e}", exc_info=True)
        return "无法分析视频内容"

def translate_text_with_ai(texts: List[str], content_analysis: str = "") -> List[str]:
    """
    使用DeepSeek API将多个英文字幕一次性翻译成中文
    
    Args:
        texts: 要翻译的英文文本列表
        content_analysis: 字幕内容分析结果
        
    Returns:
        翻译后的中文文本列表
    """
    logger.info(f"开始翻译 {len(texts)} 条字幕")
    
    # 获取API密钥
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("缺少API密钥，请设置DEEPSEEK_API_KEY环境变量")
        raise ValueError("缺少API密钥，请设置DEEPSEEK_API_KEY环境变量")
    
    # 创建OpenAI客户端
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    # 将每条字幕编号并组合成一个文本
    numbered_texts = []
    for i, text in enumerate(texts):
        numbered_texts.append(f"[{i+1}] {text}")
    
    combined_text = "\n\n".join(numbered_texts)
    logger.debug(f"准备翻译的文本总长度: {len(combined_text)} 字符")
    
    # 构建请求体，设计优化后的prompt让AI先理解内容再翻译
    system_message = """你是一位专业视频字幕翻译专家，擅长将英文字幕翻译成流畅、准确、符合中文表达习惯的中文字幕。
你的翻译既保持原文的信息和情感，又符合中文的语言习惯，特别注重专业术语的准确翻译和朗读时的流畅度。"""

    user_message = f"""请将以下英文视频字幕翻译成流畅的中文。

## 视频内容分析
{content_analysis}

## 翻译步骤

1. 首先，请通读整个字幕文件，理解视频内容、主题和上下文
2. 根据理解的上下文，将每条字幕翻译成准确、自然、符合中文表达习惯的中文
3. 保持每条字幕的独立性，但要确保整体翻译的连贯性和一致性
4. 根据视频主题和上下文，正确翻译专业术语和特定表达

## 字幕格式
- 每条字幕有唯一编号 [数字]
- 请在翻译时保留这些编号，不要修改格式
- 只翻译编号后的内容，不要添加任何其他内容

## 翻译要求
- 追求地道、流畅的中文表达
- 保持原文的信息和情感
- 专业术语应准确翻译
- 如有幽默、俚语等，尽量保留原意
- 翻译后的中文字幕内容长度应尽量保持一致，便于朗读和配音
- 避免翻译过长或过短，一般为原文长度的0.8-1.2倍
- 只返回翻译结果，不要添加解释或说明

## 字幕内容：

{combined_text}"""
    
    # 发送请求
    try:
        logger.debug("发送API请求进行翻译")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=8192,
            stream=False
        )
        
        # 解析响应
        translated_text = response.choices[0].message.content
        logger.debug(f"收到API响应，响应长度: {len(translated_text)} 字符")
        
        # 分割翻译结果
        results = parse_translated_text(translated_text, len(texts))
        logger.info(f"翻译完成，获得 {len(results)} 条翻译结果")
        return results
    
    except Exception as e:
        logger.error(f"翻译时出错: {e}", exc_info=True)
        logger.warning("由于翻译失败，将返回原文本")
        return texts  # 如果翻译失败，返回原文本

def parse_translated_text(translated_text: str, expected_count: int) -> List[str]:
    """
    解析翻译后的文本，提取每条字幕
    
    Args:
        translated_text: 翻译后的完整文本
        expected_count: 预期的字幕数量
        
    Returns:
        拆分后的字幕列表
    """
    logger.info(f"开始解析翻译结果，预期字幕数: {expected_count}")
    
    # 使用正则表达式匹配[数字]格式的编号
    pattern = r'\[(\d+)\](.*?)(?=\[\d+\]|$)'
    matches = re.findall(pattern, translated_text, re.DOTALL)
    logger.debug(f"正则表达式匹配到 {len(matches)} 个结果")
    
    # 提取翻译后的文本并按原始顺序排列
    translations = [""] * expected_count
    for match in matches:
        index = int(match[0]) - 1
        if 0 <= index < expected_count:
            translations[index] = match[1].strip()
    
    empty_count = translations.count("")
    if empty_count > 0:
        logger.warning(f"有 {empty_count} 条字幕未成功匹配")
    
    # 检查是否所有字幕都有翻译
    if "" in translations or len(translations) != expected_count:
        logger.warning("使用正则表达式解析失败，尝试按行分割")
        # 如果正则表达式无法正确匹配，尝试按行分割
        lines = translated_text.strip().split('\n')
        clean_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('```') and not line.endswith('```'):
                clean_lines.append(line)
        
        logger.debug(f"清理后得到 {len(clean_lines)} 行文本")
        
        # 重新尝试匹配
        translations = []
        current_text = ""
        
        for line in clean_lines:
            if re.match(r'^\[\d+\]', line):
                if current_text:
                    translations.append(current_text.strip())
                current_text = re.sub(r'^\[\d+\]', '', line).strip()
            else:
                current_text += " " + line
        
        # 添加最后一个字幕
        if current_text:
            translations.append(current_text.strip())
        
        logger.debug(f"按行分割解析得到 {len(translations)} 条字幕")
    
    # 如果仍然无法正确匹配，则返回原文
    if len(translations) != expected_count:
        logger.error(f"无法正确解析翻译结果，预期{expected_count}条字幕，实际解析出{len(translations)}条")
        return ["无法正确翻译"] * expected_count
    
    logger.info("翻译结果解析完成")
    return translations

def create_translated_srt(subtitles: List[Dict], translated_texts: List[str], output_path: str) -> None:
    """
    创建翻译后的SRT文件
    
    Args:
        subtitles: 原字幕数据
        translated_texts: 翻译后的文本列表
        output_path: 输出文件路径
    """
    logger.info(f"开始创建翻译后的SRT文件: {output_path}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, subtitle in enumerate(subtitles):
                f.write(f"{subtitle['id']}\n")
                f.write(f"{subtitle['timecode']}\n")
                f.write(f"{translated_texts[i]}\n\n")
        
        logger.info(f"翻译后的SRT文件已保存: {output_path}")
    except Exception as e:
        logger.error(f"创建翻译后的SRT文件失败: {e}", exc_info=True)
        raise

def save_translation_log(input_path: str, content_analysis: str, sample_translations: List[Tuple[str, str]], output_dir: str) -> str:
    """
    保存翻译过程的日志，包括内容分析和样本翻译
    
    Args:
        input_path: 输入文件路径
        content_analysis: 内容分析结果
        sample_translations: 原文和译文样本
        output_dir: 输出目录
        
    Returns:
        日志文件路径
    """
    file_name = os.path.basename(input_path)
    name, _ = os.path.splitext(file_name)
    log_path = os.path.join(output_dir, f"{name}_translation_log.txt")
    
    logger.info(f"保存翻译日志到: {log_path}")
    
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"翻译日志: {file_name}\n")
            f.write("="*50 + "\n\n")
            
            f.write("## 内容分析\n\n")
            f.write(content_analysis)
            f.write("\n\n" + "="*50 + "\n\n")
            
            f.write("## 翻译样本\n\n")
            for i, (original, translated) in enumerate(sample_translations):
                f.write(f"样本 {i+1}:\n")
                f.write(f"原文: {original}\n")
                f.write(f"译文: {translated}\n\n")
        
        logger.info("翻译日志保存成功")
    except Exception as e:
        logger.error(f"保存翻译日志失败: {e}", exc_info=True)
    
    return log_path

def translate_srt_file(input_path: str, output_path: str, log_file=None) -> str:
    """
    翻译SRT字幕文件
    
    Args:
        input_path: 输入SRT文件路径
        output_path: 输出SRT文件路径
        log_file: 日志文件路径
        
    Returns:
        输出文件的路径
    """
    # 如果提供了日志文件，设置日志记录
    if log_file:
        setup_logger(log_file)
    
    logger.info(f"开始处理字幕文件: {input_path}")
    logger.info(f"输出文件路径: {output_path}")
    
    try:
        # 解析字幕文件
        subtitles = parse_srt(input_path)
        logger.info(f"成功解析到 {len(subtitles)} 条字幕")
        
        # 提取文本进行翻译
        texts = [subtitle['text'] for subtitle in subtitles]
        
        # 先分析字幕内容
        logger.info("开始分析字幕内容...")
        content_analysis = analyze_subtitle_content(texts)
        logger.info("内容分析完成")
        
        # 一次性翻译所有字幕
        logger.info("开始翻译字幕...")
        translated_texts = translate_text_with_ai(texts, content_analysis)
        logger.info("翻译完成!")
        
        # 创建翻译后的SRT文件
        create_translated_srt(subtitles, translated_texts, output_path)
        logger.info(f"翻译后的字幕已保存至: {output_path}")
        
        # 保存翻译日志
        # 选取几个样本用于记录翻译质量
        sample_count = min(5, len(texts))
        step = max(1, len(texts) // sample_count)
        samples = [(texts[i], translated_texts[i]) for i in range(0, len(texts), step)][:sample_count]
        
        output_dir = os.path.dirname(output_path)
        log_path = save_translation_log(input_path, content_analysis, samples, output_dir)
        logger.info(f"翻译日志已保存至: {log_path}")
        
        return output_path
    
    except Exception as e:
        logger.error(f"翻译过程中发生错误: {e}", exc_info=True)
        raise

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='翻译SRT字幕文件从英文到中文')
    parser.add_argument('input_file', help='输入SRT文件路径')
    parser.add_argument('-o', '--output', help='输出SRT文件路径')
    parser.add_argument('-l', '--log', help='日志文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细日志')
    
    args = parser.parse_args()
    
    # 设置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    # 如果未指定输出文件，使用默认名称
    if not args.output:
        file_name = os.path.basename(args.input_file)
        name, ext = os.path.splitext(file_name)
        args.output = f"{name}_cn{ext}"
    
    # 如果未指定日志文件，使用默认名称
    if not args.log:
        file_name = os.path.basename(args.input_file)
        name, ext = os.path.splitext(file_name)
        args.log = f"{name}_translation.log"
    
    # 设置日志
    setup_logger(args.log, log_level)
    
    try:
        translate_srt_file(args.input_file, args.output)
        logger.info("翻译过程成功完成")
    except Exception as e:
        logger.critical(f"程序执行失败: {e}", exc_info=True)
        print(f"错误: {e}")
        exit(1)

if __name__ == "__main__":
    main() 