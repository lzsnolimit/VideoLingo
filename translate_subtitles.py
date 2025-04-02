import re
import os
from typing import List, Tuple
from langchain.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import StrOutputParser


def translate_srt_file(input_path: str, output_path: str, log_file=None, target_language:str="中文") -> str:
    """
    将SRT字幕文件翻译成目标语言
    
    Args:
        input_path: 输入SRT文件路径
        output_path: 输出SRT文件路径
        log_file: 日志文件路径，如果不为None则会记录翻译日志
        target_language: 目标语言，默认为中文
        
    Returns:
        输出文件路径
    """
    print(f"开始翻译字幕文件: {input_path} -> {output_path}")
    print(f"目标语言: {target_language}")
    
    # 读取SRT文件
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析SRT文件
    subtitle_blocks = parse_srt(content)
    print(f"共解析出 {len(subtitle_blocks)} 个字幕块")
    
    # 设置翻译提示模板
    template = """
    你是一位精通{target_language}的专业字幕翻译，尤其擅长将口语化的内容翻译成准确、自然的字幕。

    规则：
    - 准确传达原文的事实、背景和情感
    - 保留专业术语、品牌名称和人名
    - 使译文符合{target_language}的表达习惯
    - 保持字幕简洁，适合观众快速阅读
    - 只返回翻译结果，不要包含任何解释或原文

    请将以下英文字幕翻译成{target_language}：

    {text}
    
    翻译结果：
    """
    
    prompt = PromptTemplate(
        input_variables=["text", "target_language"],
        template=template
    )
    
    # 初始化LangChain模型和链
    print("初始化翻译模型...")
    llm = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        # other params...
    )
    
    # 使用RunnableSequence代替LLMChain
    chain = prompt | llm | StrOutputParser()
    
    # 翻译每个字幕块
    translated_blocks = []
    print("开始翻译字幕...")
    
    for i, (idx, timestamp, text) in enumerate(subtitle_blocks):
        print(f"正在翻译第 {i+1}/{len(subtitle_blocks)} 个字幕块 (ID: {idx})...")
        
        # 调用模型进行翻译
        translated_text = chain.invoke({"text": text, "target_language": target_language})
        translated_text = translated_text.strip()
        
        print(f"原文: {text}")
        print(f"翻译: {translated_text}")
        print("-" * 50)
        
        # 记录日志
        if log_file:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"原文: {text}\n翻译: {translated_text}\n\n")
        
        # 将翻译后的字幕块添加到结果列表
        translated_blocks.append((idx, timestamp, translated_text))
    
    # 将翻译后的字幕块重新组合成SRT格式
    translated_content = format_srt(translated_blocks)
    
    # 写入输出文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
    
    print(f"翻译完成！已保存到: {output_path}")
    if log_file:
        print(f"翻译日志已保存到: {log_file}")
    
    return output_path


def parse_srt(content: str) -> List[Tuple[str, str, str]]:
    """
    解析SRT文件内容
    
    Args:
        content: SRT文件内容
        
    Returns:
        解析后的字幕块列表，每个元素为(序号, 时间戳, 文本)的元组
    """
    # 使用正则表达式匹配SRT文件的各个部分
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n((?:.+\n)+?)(?:\n|$)'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    subtitle_blocks = []
    for match in matches:
        idx = match[0]
        timestamp = match[1]
        text = match[2].strip()
        subtitle_blocks.append((idx, timestamp, text))
    
    return subtitle_blocks


def format_srt(blocks: List[Tuple[str, str, str]]) -> str:
    """
    将字幕块列表格式化为SRT格式的字符串
    
    Args:
        blocks: 字幕块列表，每个元素为(序号, 时间戳, 文本)的元组
        
    Returns:
        SRT格式的字符串
    """
    formatted_content = ""
    for idx, timestamp, text in blocks:
        formatted_content += f"{idx}\n{timestamp}\n{text}\n\n"
    
    return formatted_content.strip()


if __name__ == "__main__":
    translate_srt_file("resources/transcripts/merger_hFZFjoX2cGg.srt", "output.srt", log_file="translation_log.txt")