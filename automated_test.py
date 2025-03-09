import requests
import time
import sys

url = 'http://127.0.0.1:5001/summarize'
headers = {'Content-Type': 'application/json'}
test_url = 'https://www.youtube.com/watch?v=KrRD7r7y7NY'

while True:
    try:
        response = requests.post(url, json={'url': test_url}, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if 'summary' in data and data['summary']:
                print("✅ 成功获取有效摘要，服务已恢复正常")
                sys.exit(0)
            else:
                print(f"⚠️ 响应缺少summary字段 | 响应内容: {response.text}")
        else:
            print(f"❌ 请求失败 | 状态码: {response.status_code} | 响应: {response.text}")
        
    except requests.exceptions.RequestException as e:
        print(f"🔴 连接异常: {str(e)}")
    except ValueError as e:
        print(f"🔴 JSON解析失败: {str(e)}")
    
    print("🕒 5秒后重试...\n")
    time.sleep(5)