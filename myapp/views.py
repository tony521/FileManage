from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, StreamingHttpResponse, Http404,HttpResponseRedirect
from django.contrib import auth
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F

from .utils import get_captcha_image, get_captcha_text
from .handles import (handle_uploaded_files, set_captcha_to_session,
                      get_session_data, set_session_data)
from .forms import (LoginForm, SignupForm, UploadForm, 
                    EditForm, IntroForm,EmailForm, CreateDirectoryForm, ConfirmForm)
from .models import Directory, File, Link, get_media_abspath

import mimetypes
from io import BytesIO
from urllib.parse import quote
import os

# you need 'brew install libmagic' under Mac OS
import magic
#二维码
import qrcode
#mail
from django.core.mail import send_mail
from django.conf import settings
"""
    根目录用 '' 表示，以去除 URL 中多余的 / 符号
"""

def test(request):
    """ 专门用于测试的页面 """
    return HttpResponse('<h1>Test successful.</h1>')


# 这里的参数直接相当于用来 reverse 了，就不要再在 login_url 里用 reverse了
@login_required
def index(request):
    """
        用户登录后，直接进入自己的根目录 root_dir
        然后将用户当前目录写入 session data。
        每次访问 index 更改目录时，session data 随之改变
    """
    user = request.user
    form = UploadForm()
    try:
        directory = user.directory_set.filter(parent=None)[0] # 根目录
    except IndexError: # 没有根目录要创建一个
        directory = Directory.create_root_dir(user)
    set_session_data(request, 'directory', directory.pk)
    context = {'user': user, 'form': form, 'directory': directory}
    return render(request, 'myapp/index.html', context=context)


@login_required
def detail(request, username, path=''):
    """
        目录或者文件的详情页
        用户名和路径足以确定唯一的文件或者目录，不需要 pk
        而且 URL 中放 pk 不太美观
        注意区别：
            File.path 不含文件名
            detail(path) 包含了文件名，因为是 URL
    """
    user = get_object_or_404(User, username=username)
    file = File.objects.filter(owner=user, path=os.path.dirname(path), name=os.path.basename(path))
    #print("打印1:",file)
    directory = Directory.objects.filter(owner=user, path=path)
    form = UploadForm()


    if file and file.count() == 1:
        file = file[0]
        context = {'user': user, 'file': file, 'is_file': True}
    elif directory and directory.count() == 1:
        directory = directory[0]
        set_session_data(request, 'directory', directory.pk)
        context = {'user': user, 'form': form, 'directory': directory, 'is_file': False}
    elif directory.count() == 0: # 主目录被删了，自动新建
        directory = Directory.create_root_dir(user)
        context = {'user': user, 'form': form, 'directory': directory, 'is_file': False}
    else:
        import pdb; pdb.set_trace()
        raise Http404

    
    return render(request, 'myapp/index.html', context)


def login(request):
    
    next_url = request.GET.get('next', reverse('myapp:index'))
    key = request.session.session_key
    try:
        real_captcha = request.session[key].get('captcha')
    except KeyError:
        real_captcha = ''

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            captcha = form.cleaned_data['captcha'].lower()

            # 判断验证码是否正确
            if real_captcha == captcha:
                user = auth.authenticate(username=username, password=password)
                if user is not None and user.is_active:
                    auth.login(request, user)
                    return redirect(next_url)
                # 密码错误
                else:
                    form.add_error('password', ValidationError('您的密码输入错误'))

            # 验证码错误
            else:
                form.add_error('captcha', ValidationError('您的验证码输入错误')) # 参数含义： field 和 错误类型

    elif request.method == 'GET':
        form = LoginForm()
        
    return render(request, 'myapp/login.html', {'form': form})


def logout(request):
    auth.logout(request)
    return redirect('myapp:login')


def signup(request):
    """
        用户注册后，产生一个根目录文件 root_dir 其值为用户名
    """
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            # 这里直接返回 User 对象，并保存了用户
            # 并且 user.is_authenticated == True
            user = form.save() 
            auth.login(request, user)

            Directory.create_root_dir(user)

            return redirect('myapp:index')
    else:
        form = SignupForm()
    return render(request, 'myapp/signup.html', {'form': form})


def captcha(request):
    """ 
        验证码保存在 session 数据中，如果随意产生 session，会使得用户退出登录
        因此，需要在 user 的现有 session 中添加，而不是创建 session。
        如果 user 没有带任何 session，那么创建。
    """

    # 自动产生 4 位的验证码，确保是小写
    cap_text = get_captcha_text()
    # 验证码保存到 session 并产生图片
    set_captcha_to_session(request, cap_text)
    cap_img = get_captcha_image(cap_text)
    cap_stream = BytesIO()
    cap_img.save(cap_stream, format='png')
    return HttpResponse(cap_stream.getvalue(), content_type="image/png")

###################
####  目录操作  ####
###################

@login_required
def mkdir(request, pk):
    """
        创建目录
    """

    current_dir = Directory.objects.get(pk=pk)

    user = request.user

    if request.method == 'GET':
        form = CreateDirectoryForm()

    elif request.method == 'POST':
        form = CreateDirectoryForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            new_dir = Directory.objects.create(
                name = name,
                owner = user,
                parent = current_dir,
                path = os.path.join(current_dir.path, name),
            )
            # 作为 url 参数的时候，去掉最开头的 '/' ，以免变成 username//test 难看
            return redirect('myapp:detail', username=user.username, path=new_dir.path)
    return render(request, 'myapp/mkdir.html', {'form': form, 'directory': current_dir})

@login_required
def rmdir(request, pk):
    """ 删除目录和下面的文件、子目录 """
    directory = get_object_or_404(Directory, pk=pk)
    parent = directory.parent

    if request.method == 'GET':
        form = ConfirmForm()
        context = {
            'directory': directory, 
            'form': form,
            'is_file': False,
        }
        return render(request, 'myapp/confirm.html', context)

    elif request.method == 'POST':
        form = ConfirmForm(request.POST)
        if form.is_valid():
            confirm = form.cleaned_data['confirm']
            if confirm == 'y':
                directory.rmdir()
                if parent: 
                    return redirect(parent.get_url())
                else: # parent 是空，说明用户删除了整个家目录，那么回首页并创建一个空的家目录
                    return redirect('myapp:index')
            else:
                return redirect(directory.get_url())


###################
####  文件操作  ####
###################

@login_required
def upload(request):

    if request.method == 'POST':
        owner = request.user
        dir_pk = get_session_data(request, 'directory')
        directory = Directory.objects.get(pk=dir_pk)

        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('files')

            handle_uploaded_files(files, owner, directory)
            return redirect('myapp:detail', username=owner.username, path=directory.path)
        
    return redirect('myapp:index')


@login_required
def download(request, pk):
    """ 一般是下载，当附带 preview=True query string 时为预览 """    

    file = get_object_or_404(File, pk=pk)
    file.downloads = file.downloads + 1
    file.save()
    buf = open(file.get_full_path(), 'rb')
    response = HttpResponse(buf)   
    response['Content-Length'] = str(file.size)
#    file1=file.id
#    data='http://47.106.75.120:82/download/'+str(file1)+''
#    img2=qrcode.make(data=data)
#    img2.save("1.jpg")

    if request.GET.get('preview'):
        filetype = mimetypes.guess_type(file.name)[0]
        if not filetype:
           filetype = 'application/octet-stream'   
        response['Content-Type'] = filetype
    else:
        response['Content-Type'] = 'application/force-download'
        response['Content-Disposition'] = 'attachment; filename={}'.format(quote(file.name))
    return response


@login_required
def preview(request, pk):
    """ 预览文件 
        Query String:
        默认是预览摘要（缩略图）: thumbnail=True
        点击后预览全文（大图）: preview=True
    """

    file = get_object_or_404(File, pk=pk)
    magic_type = magic.from_file(file.get_full_path())
#二维码
#    file1=file.id
#    data='http://47.106.75.120:82/download/'+str(file1)+''
#    img2=qrcode.make(data=data)
#    img2.save("1.jpg")
#    try:
#          file2 = File.objects.create(qrcode=file.name)
#    except:
#            return redirect(reverse(index))
    if request.GET.get('thumbnail'):
        if 'image' in magic_type:
            response = "<a target='_blank' href='{a}/{b}?preview=True'><img src='{a}/{b}''>".format(a='/download', b=pk)
            return HttpResponse(response)
        elif 'UTF-8 Unicode text' in magic_type:
            response = "<h2>{} 摘要</h2><p>{} ... ...</p>".format(file.name, open(file.get_full_path()).read(1000))
            return HttpResponse(response)
    else:
        return HttpResponse('<p>Sorry啦，这个文件不能预览</p>')


@login_required
def edit(request, pk):
    """ 暂时只支持编辑文件名
        todo: 支持移动路径、是否共享
    """

    file = get_object_or_404(File, pk=pk)
    owner = request.user

    if request.method == 'GET':
        form = EditForm({'name': file.name})
    elif request.method == 'POST':
        form = EditForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            file.name = name
            file.save()
            path = os.path.join(file.path, file.name)
            return redirect('myapp:detail', username=owner.username, path=path)

    context = {'form': form, 'file': file}
    return render(request, 'myapp/edit.html', context)


@login_required
def delete(request, pk):
    """ 提供一个页面，让用户确认 """

    file = get_object_or_404(File, pk=pk)
    directory = file.parent
    # import pdb; pdb.set_trace()
    if request.method == 'POST':
        form = ConfirmForm(request.POST)
        if form.is_valid():
            confirm = form.cleaned_data['confirm']
            if confirm == 'y':
                Link.minus_one(file) # 里面包含了删除动作
                return redirect(directory.get_url())
            else:
                return redirect(directory.get_url())
    form = ConfirmForm()
    return render(request, 'myapp/confirm.html', {'file': file, 'form': form, 'is_file': True})                

#简介
@login_required
def intro(request, pk):
    """填写文件说明
    """

    file = get_object_or_404(File, pk=pk)
    file1 = file.intro
    print("introfile:",file,file1)
    owner = request.user

    if request.method == 'GET':
        form = IntroForm({'intro': file.intro})
    elif request.method == 'POST':
        form = IntroForm(request.POST)
        if form.is_valid():
            intro = form.cleaned_data['intro']
            file.intro = intro
            file.save()
            path = os.path.join(file.path, file.intro)
            return redirect('myapp:detail', username=owner.username, path=path)

    context = {'form': form, 'file': file}
    return render(request, 'myapp/intro.html', context)
#link  to  mail
def send_url(email,name,url):
     #Need to put mail function here
#     send_mail('包分享', 'App 链接.', 'info@zlddata.cn',[email], fail_silently=False)
     print("Sharing %s with %s as %s" %(url,email,name))

@login_required
def tomail(request, pk):
    file = get_object_or_404(File, pk=pk)
    file_url = request.session.get('file_url')
    print("tomail1:",file_url)
    hostname = request.get_host()
    ID=file.id
    hurl=settings.QR_URL
    #file_url = str(hostname) + str(file_url)
    file_url  = ''+hurl+''+str(ID)+''
    eform = EmailForm(request.POST or None)
    print("tomail2:",hostname,file_url,eform)
    if eform.is_valid():
        email = eform.cleaned_data["email"]
        name = eform.cleaned_data["name"]
        send_url(email,name,file_url)
        request.session['recipentEmail'] = email
        request.session['name'] = name
        request.session['file_url'] = file_url
        return HttpResponseRedirect(reverse('myapp:thank_you'))
    context = { "eform": eform, "file_url":file_url,}
    return render(request,"myapp/tomail.html",context)
def thank_you(request):
    recipentEmail = request.session.get('recipentEmail')
    recipentName = request.session.get('name')
    file_url = request.session.get('file_url')
    context = { "recipentName": recipentName,"recipentEmail": recipentEmail, "file_url":file_url}
    return render(request,"myapp/thank_you.html",context)
#def view_file(request, id):
#    obj = get_object_or_404(File, id=id)
#    download_url = obj.get_download_url(request)
#    print("打印:",obj,download_url)
#    return render(request, 'uploader/view_file.html', {'obj': obj, 'download_url': download_url})
#def downloadr(request, id):
#    obj = get_object_or_404(File, id=id)
#
#    obj.downloads = obj.downloads + 1
#    obj.datetime = datetime.now()
#    obj.save()
#
#    #filename = obj.file.name.split('/')[-1]
#    filename = obj.name
#    response = HttpResponse(obj.file, content_type='text/plain')
#    response['Content-Disposition'] = 'attachment; filename=%s' % filename
#
#    return response

def recent_files(request, pk):
    query_results = File.objects.order_by('-datetime')[:9]
    print("打印:",query_results)
    for item in query_results:
        item.url = item.get_file_url(request)
        print("打印:",item.url)
    return render(request, 'myapp/view_files.html', {'query_results': query_results})
