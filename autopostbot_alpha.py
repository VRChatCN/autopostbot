from __future__ import print_function
import json
import os
import sys
from http.cookiejar import Cookie
import time
import datetime
from pprint import pprint
from typing import List, Dict, Any, Optional

try:#移植防呆
    import vrchatapi
    from vrchatapi.api import authentication_api
    from vrchatapi.rest import ApiException
    from vrchatapi.exceptions import UnauthorizedException
    from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
    from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
except ImportError:
    print(f"[{datetime.datetime.now()}] Missing dependency: vrchatapi. Install it with `pip install vrchatapi`.")
    sys.exit(1)

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "setting.json")

def load_settings(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_settings(path, auth_value, twofactorauth_value):
    data = {
        "auth": auth_value,
        "twofactorauth": twofactorauth_value,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data

def make_cookie(name, value):
    return Cookie(0, name, value,
                  None, False,
                  "api.vrchat.cloud", True, False,
                  "/", False,
                  False,
                  173106866300,
                  False,
                  None,
                  None, {})


def extract_world_info(data: List[Any]) -> List[Dict[str, Optional[str]]]:
    """
    从数据列表中提取每个元素的 instance_id，以及 world 字段中的 name 和 image_url。

    Args:
        data: 包含多个对象或字典的列表，每个应具有 'instance_id' 与 'world' 属性或键。

    Returns:
        由字典组成的列表，每个字典包含 'instance_id'、'name' 和 'image_url' 三个字段。
        若某个字段缺失，则其值为 None。
        若某个元素缺少 'world' 键或属性，则对应返回 {'instance_id': ..., 'name': None, 'image_url': None}。
    """
    result = []
    for item in data:
        if isinstance(item, dict):
            instance_id = item.get('instance_id')
            world = item.get('world', {})
        else:
            instance_id = getattr(item, 'instance_id', None)
            world = getattr(item, 'world', None)
        if isinstance(world, dict):
            name = world.get('name')
            image_url = world.get('image_url')
        elif world:
            name = getattr(world, 'name', None)
            image_url = getattr(world, 'image_url', None)
        else:
            name = None
            image_url = None
        result.append({'instance_id': instance_id, 'name': name, 'image_url': image_url})
    return result

settings = {}
if os.path.exists(config_path):#加载设置
    try:
        settings = load_settings(config_path)
    except (json.JSONDecodeError, OSError):
        settings = {}

auth_fetched = settings.get("auth")
twofactorauth_fetched = settings.get("twofactorauth")#cookies读入至变量
group_id = settings.get("instance_id")#将要监听与发送的群组
is_prepost_enabled = bool(settings.get("is_prepost_enabled"))#是否启用零号消息
print(f"[{datetime.datetime.now()}] Group ID: {group_id}")

start_time = datetime.datetime.now()

if auth_fetched =="" and twofactorauth_fetched=="":
    configuration = vrchatapi.Configuration(
        username='mikuwithgary',
        password='CAOhg:114514',
    )
else:
    configuration = vrchatapi.Configuration()

with vrchatapi.ApiClient(configuration) as api_client:
#init api
    if auth_fetched=="" and twofactorauth_fetched=="":
        api_client.rest_client.cookie_jar.set_cookie(
            make_cookie("auth", auth_fetched))
        api_client.rest_client.cookie_jar.set_cookie(
            make_cookie("twoFactorAuth", twofactorauth_fetched))#将本地cookies上载
    
    api_client.user_agent = "autopostbot/0.0.1 killerhatsune@gmail.com"
    auth_api = authentication_api.AuthenticationApi(api_client)
    api_instance = vrchatapi.GroupsApi(api_client)    


    try:
        current_user = auth_api.get_current_user()
        print(f"[{datetime.datetime.now()}] Logged in as: {current_user.display_name}")
    except UnauthorizedException as e:
        if e.status == 200:
            if "Email 2 Factor Authentication" in e.reason:
                auth_api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(input("Email 2FA Code: ")))
            elif "2 Factor Authentication" in e.reason:
                auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(input("2FA Code: ")))
            current_user = auth_api.get_current_user()
            print(f"[{datetime.datetime.now()}] Logged in as: {current_user.display_name}")
        else:
            print(f"[{datetime.datetime.now()}] Exception when calling API: {e}")
    except vrchatapi.ApiException as e:
        print(f"[{datetime.datetime.now()}] Exception when calling API: {e}")

    instance_list = []
    instance_list_new = []
    seen_instance_ids = set()
    poll_delay = 15 #api拉取延迟，因过小的值刷爆api，小心封号
    post_delay = 60 #post延迟，过短小心被当成野人发疯
    if is_prepost_enabled == True:#零号消息
        create_group_post_request = vrchatapi.CreateGroupPostRequest(
                    title="autopostbot_Alpha测试消息",
                    text=f"当前时刻 {datetime.datetime.now()}，服务已启动，实例监听将在180秒后开始，期间如创建房间将无法自动发帖，还请各位注意~",
                    send_notification=True,
                    visibility="public"
                ) # CreateGroupPostRequest | 
        try:
            # Create a post in a Group
            api_response = api_instance.add_group_post(group_id, create_group_post_request) 
        except ApiException as e:
            print(f"[{datetime.datetime.now()}] Exception when calling GroupsApi->add_group_post: {e}")
    
    while True:
        try:
            # Get Group Instances
            api_response = api_instance.get_group_instances(group_id)
        except ApiException as e:
            print(f"[{datetime.datetime.now()}] Exception when calling GroupsApi->get_group_instances: {e}")
            break
        
        current_worlds = extract_world_info(api_response)
        pprint(current_worlds)  # 解压并简化api返回的信息，不然stdout就会被api狠狠灌注的喵...

        if not instance_list:#instance_id记录+判断
            instance_list = current_worlds.copy()
            seen_instance_ids = {item.get('instance_id') for item in instance_list if item.get('instance_id')}
            instance_list_new = []
        else:
            instance_list_new = [item for item in current_worlds if item.get('instance_id') not in seen_instance_ids]
            if instance_list_new:
                instance_list.extend(instance_list_new)
                seen_instance_ids.update(item.get('instance_id') for item in instance_list_new if item.get('instance_id'))

        for item in instance_list_new:
            url = item.get('image_url')#后续尝试在post中带上地图封面所作出的预留
            name_new = item.get('name')
            print(f"[{datetime.datetime.now()}] New instance detected: {name_new}, {url}")

        if instance_list_new and (datetime.datetime.now() - start_time).total_seconds() > 180:  # 10 minutes = 600 seconds
            world_names = [item.get('name') for item in instance_list_new if item.get('name')]
            create_group_post_request = vrchatapi.CreateGroupPostRequest(
                title="群组新开地图",
                text="地图名 "+" ".join(world_names)+" 欢迎游玩~",
                send_notification=True,
                visibility="public"
            ) # CreateGroupPostRequest | 
            try:
            # Create a post in a Group
                api_response = api_instance.add_group_post(group_id, create_group_post_request)
            except ApiException as e:
                print(f"[{datetime.datetime.now()}] Exception when calling GroupsApi->add_group_post: {e}")
            time.sleep(post_delay)
        else:
            time.sleep(poll_delay)

        print(f"[{datetime.datetime.now()}] Refreshed!")

        instance_list_new = []



