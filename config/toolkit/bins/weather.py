#!/usr/bin/env python3
"""
Weather Skill - 获取天气信息

使用 wttr.in 服务获取指定城市的天气信息
Usage: python weather.py <city_name>
"""

import sys
import urllib.request
import urllib.error


def get_weather(city: str) -> str:
    """获取城市天气信息

    Args:
        city: 城市名称（支持中英文）

    Returns:
        天气信息字符串
    """
    try:
        # 使用 wttr.in API
        url = f"https://wttr.in/{city}?format=3"

        with urllib.request.urlopen(url, timeout=10) as response:
            weather = response.read().decode('utf-8').strip()
            return weather

    except urllib.error.URLError as e:
        return f"Error: Failed to fetch weather data - {e}"
    except Exception as e:
        return f"Error: {e}"


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python weather.py <city_name>")
        print("\nExample:")
        print("  python weather.py Beijing")
        print("  python weather.py London")
        print("  python weather.py Shanghai")
        sys.exit(1)

    city = sys.argv[1]
    weather = get_weather(city)

    # 安全输出，处理Windows GBK编码问题
    try:
        print(weather)
    except UnicodeEncodeError:
        # 如果包含无法编码的字符，使用ASCII安全模式
        print(weather.encode('ascii', 'ignore').decode('ascii'))


if __name__ == "__main__":
    main()
