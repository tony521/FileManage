from django.conf.urls import url
from . import views

app_name = 'myapp'

urlpatterns = [
    url(r'^$', views.index, name='index'),

    url(r'^test/', views.test, name='test'),

    url(r'^signup/', views.signup, name='signup'),
    url(r'^login/', views.login, name='login'),
    url(r'^logout/', views.logout, name='logout'),
    url(r'^captcha/', views.captcha, name='captcha'),    
    url(r'^upload/', views.upload, name='upload'),
    url(r'^download/(?P<pk>\d+)', views.download, name='download'),
    url(r'^preview/(?P<pk>\d+)', views.preview, name='preview'),
    url(r'^(?P<pk>\d+)/mkdir/', views.mkdir, name='mkdir'), # 创建目录
    url(r'^(?P<pk>\d+)/rmdir/', views.rmdir, name='rmdir'), # 递归地删除目录
    url(r'^(?P<pk>\d+)/edit', views.edit, name='edit'), # 编辑文件
    url(r'^(?P<pk>\d+)/delete', views.delete, name='delete'), # 编辑文件
    url(r'^(?P<pk>\d+)/intro', views.intro, name='intro'), # 简介文件
    url(r'^(?P<pk>\d+)/tomail', views.tomail, name='tomail'), # 发送链接到 邮箱
    url(r'^thank_you/$', views.thank_you, name='thank_you'),
    url(r'^(?P<pk>\d+)/recent_files/', views.recent_files, name='recent_files'),#最近上传文件
#    url('view_file/<str:id>/', views.view_file, name='view_file'),

    # 既是文件详情页，又是目录的详情页
    # 因为可以容纳的 URL pattern 类型非常多，所以一定要放到最后
    url(r'^(?P<username>[_\da-zA-Z]+)/(?P<path>.*)', views.detail, name='detail'),    
]
