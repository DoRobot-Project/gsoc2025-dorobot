coding = "utf-8"

import requests
import os
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from urllib.parse import quote
from datetime import datetime
from requests.exceptions import RequestException
import requests


class NASAuthenticator:  
    def __init__(self):
        """
        初始化NAS连接信息
        
        :param nas_ip: NAS的IP地址
        :param port: NAS的HTTP端口
        :param username: NAS用户名
        :param password: NAS密码
        """
        NAS_IP = "172.16.12.20"  # NAS的IP地址
        PORT = 5000              # HTTP端口
        USERNAME = "Administor_YAO"  # 替换为您的用户名
        PASSWORD = "Baai1988~"      # 替换为您的密码
        self.nas_ip = NAS_IP
        self.port = PORT
        self.username = USERNAME
        self.password = PASSWORD
        self.sid = None
        self.last_auth_time = None
        self.base_url = f"http://{self.nas_ip}:{self.port}/webapi"
        self.server_url="http://localhost:8080"
        self.session = requests.Session()
        self.get_auth_sid()
    
    def get_auth_sid(self):
        """
        获取认证令牌sid
        
        :return: 认证令牌(sid)
        :raises Exception: 认证失败时抛出异常
        """
        auth_url = f"http://{self.nas_ip}:{self.port}/webapi/auth.cgi"
        params = {
            "api": "SYNO.API.Auth",
            "version": "3",
            "method": "login",
            "account": self.username,
            "passwd": self.password,
            "session": "FileStation",
            "format": "sid"
        }
        
        try:
            resp = requests.get(auth_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data["success"]:
                self.sid = data["data"]["sid"]
                self.last_auth_time = datetime.now()
                return self.sid
            else:
                error_info = data.get('error', {})
                code = error_info.get('code', '未知错误码')
                error_messages = {
                    400: "无此账户或密码不正确",
                    401: "账户已禁用",
                    402: "权限拒绝",
                    403: "需要两步验证码",
                    404: "两步验证码验证失败"
                }
                message = error_messages.get(code, error_info.get('message', '未知错误'))
                raise Exception(f"认证失败: {message}（错误码：{code}）")

        except requests.exceptions.RequestException as e:
            raise Exception(f"网络错误: {str(e)}")
    
    def check_session_valid(self):
        """
        检查当前会话是否仍然有效
        
        :return: 如果会话有效返回True，否则返回False
        """
        if not self.sid:
            return False
            
        check_url = f"http://{self.nas_ip}:{self.port}/webapi/auth.cgi"
        params = {
            "api": "SYNO.API.Auth",
            "version": "1",
            "method": "check",
            "session": "FileStation",
            "_sid": self.sid
        }
        
        try:
            resp = requests.get(check_url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            print('sid')
            print(data)
            return data.get("success", False)
        except:
            return False

    def get_valid_sid(self):
        """
        获取有效的sid，如果当前会话无效则重新认证
        
        :return: 有效的认证令牌(sid)
        :raises Exception: 认证失败时抛出异常
        """
        if self.check_session_valid():
            return self.sid
        return self.get_auth_sid()
    
    def _get_error_message(self, error_code):
        """根据错误码获取错误信息"""
        error_messages = {
            100: "未知错误",
            101: "缺少API、方法或版本参数",
            102: "请求的API不存在",
            103: "请求的方法不存在",
            104: "请求的版本不支持该功能",
            105: "登录会话没有权限",
            106: "会话超时",
            107: "会话被重复登录中断",
            119: "未找到SID",
            400: "文件操作参数无效",
            408: "文件或目录不存在",
            414: "文件已存在",
            900: "删除文件/文件夹失败",
        }
        return error_messages.get(error_code, f"未知错误码: {error_code}")
    

    def list_directory(self, path, recursive=False):
        """列出目录内容"""
        try:
            #sid = self.get_valid_sid()
            params = {
                'api': 'SYNO.FileStation.List',
                'version': '2',
                'method': 'list',
                'folder_path': path,
                'additional': '["real_path","size","owner","time","perm","type"]',
                '_sid': self.sid
            }
            
            if recursive:
                params['goto_path'] = path
                
            response = requests.get(
                f"{self.base_url}/entry.cgi",
                params=params
            )
            response.raise_for_status()
            list_data = response.json()
            if not list_data['success']:
                error_code = list_data.get('error', {}).get('code', '未知错误')
                if error_code == 408:  # 没有这样的文件或目录
                    raise FileNotFoundError(f"路径不存在: {path}")
                raise Exception(f"列出目录失败: {error_code}")
            
            return list_data['data']['files']
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")
        
    def _format_size(self, size):
        """将文件大小格式化为人类可读的格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def list_files(self, folder_path):
        """列出指定文件夹中的文件和子文件夹"""
        try:
            #sid = self.get_valid_sid()
            list_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
            params = {
                "api": "SYNO.FileStation.List",
                "version": "2",
                "method": "list",
                "folder_path": folder_path,
                "additional": "[\"size\"]",
                "_sid": self.sid
            }
            
            response = requests.get(list_url, params=params)
            data = response.json()
            
            if data.get("success"):
                files = data.get("data", {}).get("files", [])
                return files
            else:
                error_code = data.get("error", {}).get("code")
                error_msg = self._get_error_message(error_code)
                print(f"列出文件失败: {error_msg}")
                return []
        except RequestException as e:
            print(f"列出文件请求出错: {str(e)}")
            return []
        
    
    def check_path_exists(self, path):
        """检查路径是否存在"""
        try:
            #sid = self.get_valid_sid()
            list_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
            params = {
                "api": "SYNO.FileStation.List",
                "version": "2",
                "method": "list",
                "folder_path": path,
                "_sid": self.sid
            }
            
            response = requests.get(list_url, params=params)
            data = response.json()
            if data.get("error", {}).get("code") == 408:
                return False
            return True
        except RequestException as e:
            print(f"检查路径 {path} 出错: {str(e)}")
            return False
        
    def check_file_exists(self, remote_path):
        """
        检查远程文件是否存在
        :param remote_path: NAS上的文件路径
        :return: 文件存在返回True，否则返回False
        """
        try:
            #sid = self.get_valid_sid()
            list_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
            params = {
                "api": "SYNO.FileStation.List",
                "version": "2",
                "method": "getinfo",
                "path": f'["{remote_path}"]',
                "_sid": self.sid
            }

            response = requests.get(list_url, params=params, timeout=10)
            data = response.json()

            if data.get("success"):
                # 检查响应中的 data 字段是否包含文件信息
                file_info = data.get("data", {}).get("files")
                print(file_info)
                if 'code' in file_info[0]:
                    if file_info[0]['code'] != 200:
                        return False
                    else:
                        return True
                elif 'isdir' in file_info[0]:
                    return True
            return False
        except RequestException as e:
            print(f"检查文件 {remote_path} 出错: {str(e)}")
            return False
        
    def ensure_path_exists(self, path):
        """确保目标路径存在，逐级创建目录"""
        #sid = self.get_valid_sid()
        current_path = ""
        for part in path.strip("/").split("/"):
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"

            # 检查当前路径是否存在
            check_result = self.check_path_exists(self.sid, current_path)
            if not check_result.get("success"):
                create_result = self.create_folder(self.sid, current_path)
                if not create_result.get("success"):
                    error_code = create_result.get("error", {}).get("code")
                    if error_code == 1100:
                        continue
                    raise Exception(f"无法创建路径 {current_path}: {create_result}")
        
    def get_directory_structure(self, path, indent=0):
        """递归获取目录结构并进行漂亮格式化"""
        try:
            items = self.list_directory(path)
        except Exception as e:
            return []
       
        structure = []
        for item in items:
            if item['path']:
                parts = item['path']
                path_ = parts.split('/')
                structure.append(path_[-1])
            else:
                pass
        return structure
    
    def download_file(self, remote_path, local_path):
        """下载单个文件"""
        try:
            if not self.check_file_exists(remote_path):
                print(f"文件 {remote_path} 不存在")
                return False
            
            #sid = self.get_valid_sid()

            # 设置本地保存路径
            if local_path is None:
                local_path = os.path.basename(remote_path)
            else:
                # 如果local_path是目录，则添加文件名
                if os.path.isdir(local_path):
                    local_path = os.path.join(local_path, os.path.basename(remote_path))

            # 创建本地目录(如果不存在)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # 构建下载URL和参数
            download_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
            params = {
                "api": "SYNO.FileStation.Download",
                "version": "2",
                "method": "download",
                "path": f'["{remote_path}"]',
                "mode": "download",
                "_sid": self.sid
            }

            # 执行下载
            print(f"正在下载文件: {remote_path} -> {local_path}")
            with requests.get(download_url, params=params, stream=True, timeout=60) as response:
                response.raise_for_status()

                # 写入文件
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                print(f"文件下载成功: {local_path}")
                return True

        except RequestException as e:
            print(f"下载文件请求出错: {str(e)}")
            return False
        except Exception as e:
            print(f"下载文件时发生错误: {str(e)}")
            return False

        
    def delete_folder(self, folder_path):
        """删除指定路径的文件夹"""
        try:
            # 获取有效SID
            #sid = self.get_valid_sid()
            
            # 检查文件夹是否为空
            files = self.list_files(folder_path)
            if files:
                print(f"文件夹 {folder_path} 不为空，无法删除。")
                return False

            delete_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
            params = {
                "api": "SYNO.FileStation.Delete",
                "version": "2",
                "method": "delete",
                "path": f"[\"{folder_path}\"]",
                "_sid": self.sid
            }

            response = requests.get(delete_url, params=params)
            data = response.json()

            if data.get("success"):
                print(f"成功删除文件夹: {folder_path}")
                return True
            else:
                error_code = data.get("error", {}).get("code")
                error_msg = self._get_error_message(error_code)
                print(f"删除文件夹 {folder_path} 失败: {error_msg}")
                return False
        except RequestException as e:
            print(f"删除文件夹请求出错: {str(e)}")
            return False
        
    def create_folder(self,path):
        """创建文件夹"""
        #sid = self.get_valid_sid()

        create_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"

        # 分离路径和文件夹名
        folder_path = os.path.dirname(path)
        folder_name = os.path.basename(path)

        params = {
            "api": "SYNO.FileStation.CreateFolder",
            "version": "2",
            "method": "create",
            "folder_path": folder_path,
            "name": folder_name,
            "force_parent": "true",
            "_sid": self.sid
        }
        try:
            resp = requests.get(create_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data['success'] == True:
                return True
            return False
        except requests.exceptions.RequestException as e:
            raise Exception(f"创建目录失败: {str(e)}")
        
    def upload_file(self, task_msg, local_file_list, remote_path_list):
        """上传单个文件到NAS，返回上传结果和文件大小"""
        #sid = self.get_valid_sid()
        if len(local_file_list) != len(remote_path_list):
            return False
        file_number = len(local_file_list)
        print(file_number)
        # 发送上传开始到云平台，文件数量
        try:
            response = self.session.post(
                f"{self.server_url}/api/upload_start",
                json = task_msg
            )
            print("发送上传开始:", response.json())
        except Exception as e:
            print(f"发送上传开始失败: {e}")
        j = 0
        for i in range(file_number):
            if not os.path.exists(local_file_list[i]):
                j += 1
                print(j)
                print(local_file_list[i])
                continue

            file_name = os.path.basename(remote_path_list[i])
            file_size = os.path.getsize(local_file_list[i])
            upload_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
            remote_path = os.path.dirname(remote_path_list[i])

            # 对路径和文件名进行编码
            #encoded_remote_path = quote(remote_path)
            #encoded_file_name = quote(file_name)

            def progress_callback(monitor):
                pass

            max_retries = 3
            for retry in range(max_retries):
                try:
                    with open(local_file_list[i], "rb") as f:
                        multipart_data = MultipartEncoder(
                            fields={
                                "api": "SYNO.FileStation.Upload",
                                "version": "2",
                                "method": "upload",
                                "path": remote_path,
                                "create_parents": "true",
                                "overwrite": "true",
                                "file": (file_name, f, "application/octet-stream")
                            }
                        )
                        #print(encoded_remote_path,encoded_file_name)
                        monitor = MultipartEncoderMonitor(multipart_data, progress_callback)
                        headers = {"Content-Type": monitor.content_type}
                        params = {"_sid": self.sid}

                        resp = requests.post(
                            upload_url,
                            params=params,
                            data=monitor,
                            headers=headers,
                            timeout=600
                        )
                        print(resp.json())
                        if resp.json().get("success"):
                            break
                        else:
                            if retry < max_retries - 1:
                                print(f"\n上传出错，第 {retry + 1} 次重试")
                            else:
                                j += 1
                                print(f"\n上传出错，达到最大重试次数")
                except Exception as e:
                    if retry < max_retries - 1:
                        print(f"\n上传出错，第 {retry + 1} 次重试: {str(e)}")
                    else:
                        j += 1
                        print(f"\n上传出错，达到最大重试次数: {str(e)}")
            if (i+1) % 3 == 0 and i != file_number - 1:
                task_msg['total_file_count'] = file_number
                task_msg['failed_file_count'] = j
                task_msg['success_file_count'] = i+1 - j
                try:
                    response = self.session.post(
                        f"{self.server_url}/api/upload_process",
                        json=task_msg
                    )
                    print("发送上传过程:", response.json())
                except Exception as e:
                    print(f"发送上传过程失败: {e}")
            elif i == file_number - 1:
                task_msg['total_file_count'] = file_number
                task_msg['failed_file_count'] = j
                task_msg['success_file_count'] = i+1-j
                try:
                    response = self.session.post(
                        f"{self.server_url}/api/upload_process",
                        json=task_msg
                    )
                    print("发送上传过程:", response.json())
                except Exception as e:
                    print(f"发送上传过程失败: {e}")
        if j != 0:
            try:
                response = self.session.post(
                    f"{self.server_url}/api/upload_fail",
                    json=task_msg
                )
                print("发送上传失败:", response.json())
            except Exception as e:
                print(f"发送上传失败失败: {e}")
        else:
            try:
                response = self.session.post(
                    f"{self.server_url}/api/upload_finish",
                    json=task_msg
                )
                print("发送上传成功:", response.json())
            except Exception as e:
                print(f"发送上传成功失败: {e}")
        

    def upload_test(self,local_file, remote_path):
        #sid = self.get_valid_sid()
        file_name = os.path.basename(local_file)
        file_size = os.path.getsize(local_file)
        upload_url = f"http://{self.nas_ip}:{self.port}/webapi/entry.cgi"
        encoded_remote_path = quote(remote_path)
        encoded_file_name = quote(file_name)
        def progress_callback(monitor):
                pass
        try:
            with open(local_file, "rb") as f:
                multipart_data = MultipartEncoder(
                    fields={
                        "api": "SYNO.FileStation.Upload",
                        "version": "2",
                        "method": "upload",
                        "path":remote_path,
                        "create_parents": "true",
                        "overwrite": "true",
                        "file": (encoded_file_name, f, "application/octet-stream")
                    }
                )

                monitor = MultipartEncoderMonitor(multipart_data, progress_callback)
                headers = {"Content-Type": monitor.content_type}
                params = {"_sid": self.sid}

                resp = requests.post(
                    upload_url,
                    params=params,
                    data=monitor,
                    headers=headers,
                    timeout=600
                )
                print(resp.json())
                return resp.json().get("success"), file_size
        except Exception as e:
            print(f"\n上传出错，达到最大重试次数: {str(e)}")

    

        
# if __name__ =="__main__":
#     nas_auth = NASAuthenticator()
#     nas_auth.get_directory_structure("/传输路径/ceshi/cache/1813490901")
#     # structure = nas_auth.get_directory_structure("/传输路径/ceshi/cache") # dir
#     # print(structure)
#     #download_msg = nas_auth.download_file("/传输路径/ceshi/meta/info.json","/home/liuyou/agilex/")
#     # print(download_msg)
#     # delete_msg = nas_auth.delete_folder("/传输路径/ceshi/cache")
#     # print(delete_msg)
#     #print(nas_auth.check_path_exists("/传输路径/ceshi/meta"))
#     #print(nas_auth.create_folder("/传输路径/ceshi/cache"))
#    nas_auth.upload_test("/home/liuyou/Documents/local_to_nas/aloha-1/20250624/1813490901/videos/chunk-000/observation.images.image_top/episode_000000.mp4","/传输路径/ceshi/collect_data/叠衣服_1813490901/videos/chunk-000/observation.images.image_top")
    # nas_auth.check_file_exists('/传输路径/ceshi/collect_data/叠衣服_1813490901/meta')
    