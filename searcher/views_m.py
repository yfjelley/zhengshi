# coding=utf-8

import MySQLdb
import datetime
from itertools import chain
import json
import os,re
import random

from django.core.serializers.json import DjangoJSONEncoder
from DjangoCaptcha import Captcha
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.urlresolvers import reverse
from PIL import Image
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import get_template
from django.core.files.storage import FileSystemStorage
from ddbid.settings import EMAIL_HOST_USER, EMAIL_HOST_PASSWORD

from searcher.forms import ContactForm, SearchForm, LoginForm, UserInformationForm, RegisterForm, ForgetPWForm,ModfiyPWForm,ModfiyPForm
from searcher.inner_views import index_loading, index_loading_m,data_filter, result_sort, get_pageset, get_user_filter, user_auth, \
    refresh_header, send_flow_all
from searcher.models import Bid, UserFavorite, Platform, UserInformation, DimensionChoice, UserFilter, UserReminder, \
    WeekHotSpot, BidHis, ReminderUnit
from ddbid import conf


__author__ = 'pony'

storage = FileSystemStorage(
    location=conf.UPLOAD_PATH,
    base_url='/static/upload/'
)



def index(request):

    results_right = Bid.objects.filter(process__lt=100).filter(term__gt=0).order_by("random_rank").order_by("term")[0:4]
    results_right.query.group_by = ['platform_id']

    results_left = Bid.objects.filter(process__lt=100).order_by("random_rank").order_by("-income_rate")[0:4]
    results_left.query.group_by = ['platform_id']
    form = SearchForm()
    print form
    return render_to_response('index_m.html', {'results_left':results_left,'results_right':results_right,'form':form},
                                  context_instance=RequestContext(request))

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            send_mail(
                cd['subject'],
                cd['message'],
                cd.get('email', 'noreply@example.com'),
                ['siteowner@example.com'],
            )
            return HttpResponseRedirect('/contact/thanks/')
    else:
        form = ContactForm(initial={'subject': 'I love your site!'})
    return render_to_response('contact_form.html', {'form': form}, context_instance=RequestContext(request))


def login(request):
    print "this is test"
    if request.method == 'POST':
        username = request.REQUEST.get('log_un', None)
        pwd = request.REQUEST.get('log_pwd', None)
        code = request.REQUEST.get('log_code', None)
        if username is None:
            form = LoginForm(request.POST)
            if form.is_valid():
                cd = form.clean()
                username = cd['username']
                pwd = cd['password']
                code = cd['vcode']
                i = user_auth(request, username, pwd, code)
                if i == 1:
                    a = request.REQUEST.get('next', None)
                    if a:
                        return HttpResponseRedirect(a)
                    else:
                        return HttpResponseRedirect(reverse('search_result_m'))
                else:
                    form.valiatetype(i)
                    return render_to_response('login_m.html', {'form': form, },
                                              context_instance=RequestContext(request))
            else:
                return render_to_response('login_m.html', {'form': form, },
                                          context_instance=RequestContext(request))

        return refresh_header(request, user_auth(request, username, pwd, code))
    else:
        form = LoginForm()
        next = request.GET.get('next', None)
        return render_to_response('login_m.html', {'form': form, 'next': next},
                                  context_instance=RequestContext(request))

def forgetpw(request):
    if request.method == 'POST':
        form = ForgetPWForm(request.POST)
        if form.is_valid():
            cd = form.clean()
            username = cd['username']
            _code = request.session.get('sms_code')
            smscode = cd['smscode']
            user = User.objects.get(username=username)
            pw = user.userinformation.abcdefg


            if pw is not None and _code == int(smscode):
                user = auth.authenticate(username=username, password=pw)
                if user is not None and user.is_active:
                    auth.login(request, user)
                    #return HttpResponse(u'登录成功')
                    return HttpResponseRedirect(reverse('search_result_m'))
                else:
                    return HttpResponse(u'输入错误')
                    #return render_to_response('forgetpwd.html',{"form":form},
                      #                context_instance=RequestContext(request))

            else:
                form.valiatetype(2)
                return render_to_response('forget_password_m.html',{"form":form},
                                      context_instance=RequestContext(request))

        else:
            return render_to_response('forget_password_m.html', {'form': form}, context_instance=RequestContext(request))
    else:
        form = ForgetPWForm()
        return render_to_response('forget_password_m.html', {'form': form}, context_instance=RequestContext(request))


def verifycode(request):
    figures = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    ca = Captcha(request)
    ca.words = [''.join([str(random.sample(figures, 1)[0]) for i in range(0, 4)])]
    ca.type = 'word'
    ca.img_width = 60
    ca.img_height = 20
    return ca.display()


def checkvcode(request):
    if_vcode = request.POST.get('name', None)
    _code = request.session.get('_django_captcha_key')
    if if_vcode:
        response = HttpResponse()
        response['Content-Type'] = "application/json"
        vcode = request.POST.get('param', None)
        if _code.lower() == vcode.lower():
            response.write('{"info": "","status": "y"}')
            return response
        else:
            response.write('{"info": "验证码错误","status": "n"}')
            return response

def checksmscode(request):
    if_smscode = request.POST.get('name', None)
    _code = request.session.get("sms_code")
    if if_smscode:
        response = HttpResponse()
        response['Content-Type'] = "application/json"
        smscode = request.POST.get('param', None)
        if _code  == int(smscode):
            response.write('{"info": "","status": "y"}')
            return response
        else:
            response.write('{"info": "验证码错误","status": "n"}')
            return response


def checkuser(request):
        response = HttpResponse()
        print "checkuser"
        response['Content-Type'] = "text/javascript"
        u_ajax = request.POST.get('name', None)
        if u_ajax:
            response['Content-Type'] = "application/json"
            r_u = request.POST.get('param', None)
            u = User.objects.filter(username=r_u)
            print "xxxxxxxxxxx"
            if u.exists():
                response.write('{"info": "","status": "y"}')
                return response
            else:
                print "ddddddddd"
                response.write('{"info": "用户不存在","status": "n"}')  # 用户不存在
                return response

def checkuser_phone(request):
        response = HttpResponse()
        response['Content-Type'] = "text/javascript"
        u_ajax = request.POST.get('name', None)
        if u_ajax:
            response['Content-Type'] = "application/json"
            r_u = request.POST.get('param', None)
            u = User.objects.filter(username=r_u)
            print "xxxxxxxxxxx"
            if u.exists():
                response.write('{"info": "用户已存在","status": "n"}')  # 用户已存在
                return response
            else:
                print "ddddddddd"
                response.write('{"info": "","status": "y"}')
                return response

def register(request):
    if request.method == 'POST':
        response = HttpResponse()
        response['Content-Type'] = "text/javascript"
        u_ajax = request.POST.get('name', None)
        if u_ajax:
            response['Content-Type'] = "application/json"
            r_u = request.POST.get('param', None)
            u = User.objects.filter(username=r_u)
            if u.exists():
                response.write('{"info": "用户已存在","status": "n"}')  # 用户已存在
                return response
            else:
                response.write('{"info": "用户可以使用","status": "y"}')
                return response
        form = RegisterForm(request.POST)

        if form.is_valid():
            cd = form.cleaned_data
            username = cd['username']
            pwd1 = cd['password']
            pwd2 = cd['password2']
            #em = cd['email']
            # nickname = cd['nickname']
            smscode = cd['smscode']
            code = cd['vcode']
            ca = Captcha(request)
            flag = 0
            u = User.objects.filter(username=username)
            f = ca.check(code)
            if u.exists():
                form.valiatetype(2)
                flag = 1
            if pwd1 != pwd2:
                form.valiatetype(3)
                flag = 1
            if not f:
                form.valiatetype(4)
                flag = 1
            if flag == 1:
                return render_to_response("reg_m.html", {'form': form}, context_instance=RequestContext(request))
            elif pwd1 == pwd2 and f:
                new_user = User.objects.create_user(username=username, password=pwd1)
                new_user.save()
                # initial={'photo_url': '/static/upload/default.png'}
                u = UserInformation(user=new_user, photo_url='/static/upload/default.png', abcdefg=pwd1)
                u.save()
                user = auth.authenticate(username=username, password=pwd1)
                auth.login(request, user)
                send_flow_all(username)
                p = re.compile('^13[4-9][0-9]{8}|^15[0,1,2,7,8,9][0-9]{8}|^18[2,7,8][0-9]{8}|^147[0-9]{8}|^178[0-9]{8}')
                p1 = re.compile('^18[0,1,9][0-9]{8}|^133[0-9]{8}|^153[0-9]{8}|^177[0-9]{8}')
                phone = username
                if p.match(str(phone)):
                    flag1 = 1
                elif p1.match(str(phone)):
                    flag1 = 2
                else:
                    flag1 = 3
                return  render_to_response("reg_success_m.html", {'flag1':flag1}, context_instance=RequestContext(request))
        else:
            return render_to_response("reg_m.html", {'form': form}, context_instance=RequestContext(request))
    else:
        form = RegisterForm()
        return render_to_response("reg_m.html", {'form': form}, context_instance=RequestContext(request))


@login_required
def logout(request):
    """

    :param request:
    :return:
    """
    auth.logout(request)
    return HttpResponseRedirect(reverse('searchindex'))


@login_required
def add_favoritebid(request, objectid):
    user_id = auth.get_user(request).id
    user = User.objects.get(id=user_id)
    ftype = 1
    u = UserFavorite.objects.filter(user_id=user_id, favorite_type=ftype, favorite_id=objectid)
    if u.exists():
        return HttpResponse(u'已经收藏过了')

    u1 = UserFavorite(user_id=user_id, favorite_type=ftype, favorite_id=objectid)
    u1.save()
    return HttpResponse(u'收藏成功')


@login_required
def add_favoriteplatform(request, objectid):
    user_id = auth.get_user(request).id
    user = User.objects.get(id=user_id)
    ftype = 2
    u = UserFavorite.objects.filter(user_id=user_id, favorite_type=ftype, favorite_id=objectid)
    if u.exists():
        return HttpResponse(u'已经收藏过了')
    u1 = UserFavorite(user_id=user_id, favorite_type=ftype, favorite_id=objectid)
    u1.save()
    return HttpResponse(u'收藏成功')


@login_required
def add_reminder(request, objectid):
    user = auth.get_user(request)
    try:
        u_r = UserReminder.objects.get(user=user, bid=objectid)
        return HttpResponse(u'已存在')
    except ObjectDoesNotExist:
        u_r = UserReminder(user=user, bid=objectid, reminder=1, value=1, status=1)
        u_r.save()
        return HttpResponse(u'已添加')


@login_required
def del_reminder(request, objectid):
    user = auth.get_user(request)
    try:
        u_r = UserReminder.objects.get(user=user, bid=objectid)
        u_r.delete()
        return HttpResponse(u'已删除')
    except ObjectDoesNotExist:
        return HttpResponse(u'不存在')


@login_required
def do_reminder(request):
    user = auth.get_user(request)
    days = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
            30, 31]
    if request.method == 'POST':
        b_id = request.POST.get('bid', None)
        method = request.POST.get('method', None)
        rtype = request.POST.get('type', None)
        if method == 'add':
            try:
                u_r = UserReminder.objects.get(user=user, bid_id=int(b_id), reminder_id=int(rtype))
                return HttpResponse(u'已存在')
            except ObjectDoesNotExist:
                if rtype == u'1' or rtype == u'2' or rtype == u'3':
                    value = 1
                else:
                    value = 0
                u_r = UserReminder(user=user, bid_id=int(b_id), reminder_id=int(rtype), value=value, status=1)
                u_r.save()
                return HttpResponse(u'已添加')
        elif method == 'active':
            try:
                u_r = UserReminder.objects.filter(user=user, bid_id=int(b_id)).update(status=1)
                return HttpResponse(u'提醒已打开')
            except ObjectDoesNotExist:
                return HttpResponse(u'不存在')
        elif method == 'inactive':
            try:
                u_r = UserReminder.objects.filter(user=user, bid_id=int(b_id)).update(status=0)
                return HttpResponse(u'提醒已关闭')
            except ObjectDoesNotExist:
                return HttpResponse(u'不存在')
        elif method == 'del':
            try:
                u_r = UserReminder.objects.filter(user=user, bid_id=int(b_id))
                u_r.delete()
                return HttpResponse(u'已删除')
            except ObjectDoesNotExist:
                return HttpResponse(u'不存在')
        elif method == 'change':
            a = request.POST.getlist('params[]')
            r_u = ReminderUnit.objects.all().order_by('id')
            i = 0
            for r in r_u:
                try:
                    u_r = UserReminder.objects.get(user=user, bid_id=int(b_id), reminder_id=r.id)
                except ObjectDoesNotExist:
                    u_r = UserReminder(user=user, bid_id=int(b_id), reminder_id=r.id)
                if int(a[i]) == 0:
                    u_r.value = 0
                    u_r.status = 1
                else:
                    u_r.value = a[i]
                    u_r.status = 1
                if int(a[i]) != u_r.value:
                    u_r.is_reminded = 0
                u_r.save()
                i += 1
            return HttpResponse(u'修改已保存')
    else:
        reminders = UserReminder.objects.filter(user=user)
        flag = 2
        aa = []
        bb = {}
        if len(reminders) > 0:
            t = reminders[0].bid_id
            for a in reminders:
                if a.bid_id == t:
                    bid = Bid.objects.filter(id=a.bid_id)
                    if not bid.exists():
                        bid = BidHis.objects.filter(id=a.bid_id)

                    if a.reminder_id == 1:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'a': a.value}
                    elif a.reminder_id == 2:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'b': a.value}
                    elif a.reminder_id == 3:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'c': a.value}
                    elif a.reminder_id == 4:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'd': a.value}
                    elif a.reminder_id == 5:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'e': a.value}
                    bb.update(ttt)
                    t = a.bid_id
                else:
                    aa.append(bb)
                    bb = {}
                    bid = Bid.objects.filter(id=a.bid_id)
                    if not bid.exists():
                        bid = BidHis.objects.filter(id=a.bid_id)
                    if a.reminder_id == 1:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'a': a.value}
                    elif a.reminder_id == 2:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'b': a.value}
                    elif a.reminder_id == 3:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'c': a.value}
                    elif a.reminder_id == 4:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'd': a.value}
                    elif a.reminder_id == 5:
                        ttt = {'bid_id': a.bid_id, 'bid_name': bid[0].name, 'status': a.status, 'e': a.value}
                    bb.update(ttt)
                    t = a.bid_id
            aa.append(bb)
        return render_to_response("user_reminder.html", {'reminders': aa, 'flag': flag, 'days': days},
                                  context_instance=RequestContext(request))


@login_required
def myfavorite(request, tid):
    flag = int(tid)
    favorites = {}
    userid = auth.get_user(request).id
    userfavoriteBid = UserFavorite.objects.filter(user=userid, favorite_type=1).values("favorite_id")
    userfavoriteplatform = UserFavorite.objects.filter(user=userid, favorite_type=2).values("favorite_id")
    favoriteBidNow = Bid.objects.filter(id__in=userfavoriteBid)
    favoriteBidHis = BidHis.objects.filter(id__in=userfavoriteBid)
    favoriteplatform = Platform.objects.filter(id__in=userfavoriteplatform)
    if flag == 4:
        favorites = list(chain(favoriteBidNow, favoriteBidHis))
    else:
        favorites = favoriteplatform
    return render_to_response("user_favorite.html",
                              {'favorites': favorites, 'flag': flag}, context_instance=RequestContext(request))


def platform(request):
    pfs = Platform.objects.all()
    return render_to_response("platform.html", {'platforms': pfs}, context_instance=RequestContext(request))


@login_required
def userinformation(request):
    url = None
    user = auth.get_user(request)
    flag = 1
    if request.method == 'POST':
        form = UserInformationForm(request.POST)
        f = request.FILES.get('file', None)
        if f:
            extension = os.path.splitext(f.name)[-1]
            msg = None
            if f.size > 1048576:
                msg = u"图片大小不能超过1MB"
            if (extension not in ['.jpg', '.png', '.gif', '.JPG', '.PNG', '.GIF']) or ('image' not in f.content_type):
                msg = u"图片格式必须为jpg，png，gif"
            if msg:
                return render_to_response("user_information.html", {'form': form, 'flag': flag, 'error': msg},
                                          context_instance=RequestContext(request))

            im = Image.open(f)
            im.thumbnail((120, 120))
            name = 'photo' + storage.get_available_name(str(user.id)) + '.png'
            im.save('%s/%s' % (storage.location, name), 'PNG')
            url = storage.url(name)
            # print(url)

        if form.is_valid():
            try:
                u_i = UserInformation.objects.get(user=user)
                form1 = UserInformationForm(request.POST, instance=u_i)
                u_i = form1.save(commit=False)
                if url:
                    u_i.photo_url = url

            except ObjectDoesNotExist:
                u_i = form.save(commit=False)
                u_i.user = user
                u_i.photo_url = url
            u_i.save()
            return render_to_response("user_information.html", {'form': form,"msg":u"保存成功",'user':user})
        else:
            return render_to_response("user_information.html", {'form': form, "msg":u"保存失败",'flag': flag,'user':user},
                                      context_instance=RequestContext(request))
        #return HttpResponseRedirect(reverse('userinformation'))
        return render_to_response("user_information.html", {'form': form,"msg":u"保存成功",'user':user})
    else:
        try:
            form = UserInformationForm(instance=user.userinformation)
        except ObjectDoesNotExist:
            form = UserInformationForm()
            # print(form)
    return render_to_response("user_information.html", {'form': form, 'flag': flag},
                              context_instance=RequestContext(request))


@login_required
def save_filter(request):
    user = auth.get_user(request)
    if request.method == 'POST':
        method = request.REQUEST.get('method', None)
        fid = request.REQUEST.get('fid', None)
        name = request.REQUEST.get('name', None)
        params = str(','.join(request.POST.getlist('params[]')))
        if method == 'add':
            f_l = UserFilter.objects.filter(user=user)
            num = len(f_l)
            if 0 == num:
                t = UserFilter(user=user, filter_order=1, choices=params, name=name)
            # t = UserFilter(user=user, filter_order=1, choice_yr_id=yieldrate_id, choice_tm_id=time_id)
            elif 5 <= num:
                return HttpResponse(u'最多只能保存5个')
            else:
                for f in f_l:
                    if str(f.choices) == params:
                        return HttpResponse(u'已经保存过了')
                t = UserFilter(user=user, filter_order=num + 1, choices=params, name=name)
            t.save()
            return HttpResponse(u'保存成功')
        elif method == 'rename':
            f_l = UserFilter.objects.get(id=fid)
            f_l.choices = params
            f_l.name = name
            f_l.save()
            return HttpResponse(u'修改成功')
    else:

        flag = 3
        f_l = get_user_filter(user)
        dimensions = DimensionChoice.objects.all()
        return render_to_response("user_shortcut.html", {'f_ls': f_l, 'flag': flag, 'dimensions': dimensions},
                                  context_instance=RequestContext(request))


@login_required
def del_filter(request, fid):
    try:
        u = UserFilter.objects.get(id=fid)
        u.delete()
        return HttpResponse(u'1')
    except:
        return HttpResponse(u'2')


def bid_detail(request, objectid):
    try:
        b = Bid.objects.get(id=objectid)
    except ObjectDoesNotExist:
        b = BidHis.objects.get(id=objectid)
    now_date = datetime.datetime.now()
    yes_time_1 = now_date + datetime.timedelta(days=-1)
    connection = MySQLdb.connect(host="ddbid2015.mysql.rds.aliyuncs.com", user="django", passwd="ddbid_django1243", db="ddbid_db")
    cursor = connection.cursor()
    arr_money = []
    arr_mount = []
    arr_day = []
    if b.platform.id != 13:
        sql = "select day_id,amount,inv_quantity from t_platform_info_daily where platform_id=%d order by day_id" %(b.platform.id)
    else:
        sql = 'select day_id,amount,inv_quantity from t_platform_info_daily where platform_id=10 order by day_id'
    cursor.execute(sql)
    cds = cursor.fetchall()
    i = 0
    for abc in cds:
        i += 1

        money = {'money%d' % i: abc[1]}
        mount = {'amount%d' % i: abc[2]}
        day = {'day%d' % i: abc[0]}
        arr_money.append(money)
        arr_mount.append(mount)
        arr_day.append(day)

    json_money = json.dumps(arr_money, cls=DjangoJSONEncoder)
    json_mount = json.dumps(arr_mount, cls=DjangoJSONEncoder)
    json_day = json.dumps(arr_day, cls=DjangoJSONEncoder)
    cursor.close()
    return render_to_response("bid_detail_m.html",
                              {'bid': b, 'json_money': json_money, 'json_mount': json_mount, 'json_day': json_day},
                              context_instance=RequestContext(request))


def bid_detail_p(request):
    objectid = request.POST.get('object_id')
    try:
        b = Bid.objects.get(id=objectid)
    except ObjectDoesNotExist:
        try:
            b = BidHis.objects.get(id=objectid)
        except:
            return HttpResponse()
    return HttpResponse(u'1')

def comb_detail(request, ids):
    if ids is None:
        return HttpResponse(u'1')
    ids = ids.split('&')
    bids = Bid.objects.filter(id__in=ids)
    return render_to_response('comb_detail.html', {'bids': bids}, context_instance=RequestContext(request))


@login_required
def shortcut_request(request, objectid):
    filters = UserFilter.objects.get(id=objectid).choices
    index_parts = index_loading(None, filters, 1)
    return render_to_response('search_result.html',
                              {'results': index_parts.get('results'), 'dimensions': index_parts.get('dimensions'),
                               'c_results': index_parts.get('c_result'), 'params': filters,
                               'last_page': index_parts.get('last_page'),
                               'page_set': index_parts.get('page_set')},
                              context_instance=RequestContext(request))


def contact_us(request):
    return render_to_response('contact_us.html', context_instance=RequestContext(request))


def about_us(request):
    return render_to_response('about_us.html', context_instance=RequestContext(request))

def disclaimer(request):
    return render_to_response('disclaimer.html', context_instance=RequestContext(request))

def phone_infoPage(request):
    return render_to_response('test_phone.html', context_instance=RequestContext(request))

def user_updatepwd(request):
    form = ModfiyPWForm()
    return render_to_response('user_updatepwd.html',{'form':form}, context_instance=RequestContext(request))

import urllib2, urllib, hashlib, random
def send_smscode(request):
    phoneNum = request.POST.get('phoneNum', '')
    m = hashlib.md5()
    m.update('shcdjr2')
    random_code = random.randint(1000, 9999)
    request.session["sms_code"] = random_code
    content = "您的验证码是：%s，有效期为五分钟。如非本人操作，可以不用理会"%random_code
    print content
    data = """
              <Group Login_Name ="%s" Login_Pwd="%s" OpKind="0" InterFaceID="" SerType="xxxx">
              <E_Time></E_Time>
              <Item>
              <Task>
              <Recive_Phone_Number>%d</Recive_Phone_Number>
              <Content><![CDATA[%s]]></Content>
              <Search_ID>111</Search_ID>
              </Task>
              </Item>
              </Group>
           """ % ("shcdjr", m.hexdigest().upper(), int(phoneNum), content.decode("utf-8").encode("GBK"))

    cookies = urllib2.HTTPCookieProcessor()
    opener = urllib2.build_opener(cookies)
    request = urllib2.Request(
                               url = r'http://userinterface.vcomcn.com/Opration.aspx',
                               headers= {'Content-Type':'text/xml'},
                               data = data
                              )
    print opener.open(request).read()
    return HttpResponse()

def send_smscode_modify(request):
    phoneNum = request.POST.get('phoneNum', '')
    user = User.objects.filter(username=int(phoneNum))
    print user
    if not len(user):
        print "ceshi"
        m = hashlib.md5()
        m.update('shcdjr2')
        random_code = random.randint(1000, 9999)
        request.session["sms_code"] = random_code
        content = "您的验证码是：%s，有效期为五分钟。如非本人操作，可以不用理会"%random_code
        print content
        data = """
                  <Group Login_Name ="%s" Login_Pwd="%s" OpKind="0" InterFaceID="" SerType="xxxx">
                  <E_Time></E_Time>
                  <Item>
                  <Task>
                  <Recive_Phone_Number>%d</Recive_Phone_Number>
                  <Content><![CDATA[%s]]></Content>
                  <Search_ID>111</Search_ID>
                  </Task>
                  </Item>
                  </Group>
               """ % ("shcdjr", m.hexdigest().upper(), int(phoneNum), content.decode("utf-8").encode("GBK"))

        cookies = urllib2.HTTPCookieProcessor()
        opener = urllib2.build_opener(cookies)
        request = urllib2.Request(
                                   url = r'http://userinterface.vcomcn.com/Opration.aspx',
                                   headers= {'Content-Type':'text/xml'},
                                   data = data
                                  )
        print "send phone"
        print opener.open(request).read()
    else:
        print "xxxxxxxxxxxxxxxxx"
    return HttpResponse()

def safecenter(request):
    #print "safecenter:", request
    if request.method =="POST":
        form = ModfiyPWForm(request.POST)
        if form.is_valid():
            print "form is valid"
            username = request.user.username
            print username

            user = User.objects.get(username=username)
            pw = user.userinformation.abcdefg
            print  pw,user

            cd = form.cleaned_data
            password = cd['password']
            password2 = cd['password2']

            if int(password) == int(password2) :
                user = auth.authenticate(username=username, password=pw)
                if user is not None and user.is_active:
                    user.set_password(password)
                    user.save()
                    user.userinformation.abcdefg = password
                    user.userinformation.save()
                    t = get_template('success.html')
                    content_html = t.render(
                            RequestContext(request,{'form':form,'status':u'密码修改成功！'}))

                    payload = {
                            'content_html': content_html,
                            'success': True,
                        }
                    return HttpResponse(json.dumps(payload), content_type="application/json")

            else:
                print "is not valid"
                t = get_template('success.html')
                content_html = t.render(
                        RequestContext(request,{'form':form,'status':u'两次输入密码不一致'}))

                payload = {
                        'content_html': content_html,
                        'success': True,
                    }
                return HttpResponse(json.dumps(payload), content_type="application/json")
        else:
            print "form error",form.errors
            print "form is not valid kkkkkk"

            print "xxxxxxxxxxxxxxxx"
            t = get_template('success.html')
            content_html = t.render(
                    RequestContext(request,{'form':form,'status':u'输入非法！'}))

            payload = {
                    'content_html': content_html,
                    'success': True,
                }
            return HttpResponse(json.dumps(payload), content_type="application/json")

    else:
        print "safecenter"
        form = ModfiyPWForm()
        t = get_template('safecenter.html')
        content_html = t.render(
                RequestContext(request,{'form':form}))

        payload = {
                'content_html': content_html,
                'success': True,
            }
        return HttpResponse(json.dumps(payload), content_type="application/json")


def change_phone_number(request):
    if request.method == "POST":
        form = ModfiyPForm(request.POST)
        print dir(form)
        print form.errors
        if form.is_valid():
            cd = form.clean()
            username = cd['username']
            _code = request.session.get('sms_code')
            smscode = cd['smscode']

            print _code ,smscode

            if  _code == int(smscode) :
                user = auth.get_user(request)
                user.username = username
                user.save()
                t = get_template('success.html')
                content_html = t.render(
                        RequestContext(request,{'form':form,'status':u'手机号修改成功！'}))

                payload = {
                        'content_html': content_html,
                        'success': True,
                    }
                return HttpResponse(json.dumps(payload), content_type="application/json")
            else:
                t = get_template('success.html')
                content_html = t.render(
                        RequestContext(request,{'form':form,'status':u'验证码错误！'}))

                payload = {
                        'content_html': content_html,
                        'success': True,
                    }
                return HttpResponse(json.dumps(payload), content_type="application/json")

        else:
            t = get_template('success.html')
            content_html = t.render(
                    RequestContext(request,{'form':form,'status':u'非法输入！'}))

            payload = {
                    'content_html': content_html,
                    'success': True,
                }
            return HttpResponse(json.dumps(payload), content_type="application/json")
    else:
        form = ModfiyPForm()
        t = get_template('changephone.html')
        content_html = t.render(
                RequestContext(request,{'form':form}))

        payload = {
                'content_html': content_html,
                'success': True,
            }
        return HttpResponse(json.dumps(payload), content_type="application/json")

def search(request):
    form = SearchForm()
    t = get_template('search_m.html')
    content_html = t.render(
            RequestContext(request,{'form':form}))

    payload = {
            'content_html': content_html,
            'success': True,
        }
    return HttpResponse(json.dumps(payload), content_type="application/json")

def detail_search(request):

    if request.GET.get('page', None) is not None:
        params = ','.join(request.GET.getlist('params[]'))
        a = params.split(',')
        sorttype = request.REQUEST.get('sorttype', None)
        sortorder = request.REQUEST.get('sortorder', None)
        amount = request.REQUEST.get('amount', None)
        if amount:
            results = Bid.objects.filter(amount__gte=amount).order_by("random_rank").order_by("amount")
        else:
            results = Bid.objects.all().order_by("random_rank")
        filters = DimensionChoice.objects.filter(id__in=a)
        results = data_filter(results, filters)
        if sorttype is not None and sortorder is not None:
            results = result_sort(results, sorttype, sortorder)
        ppp = Paginator(results, 3)
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        try:
            results = ppp.page(page)
        except (EmptyPage, InvalidPage):
            results = ppp.page(ppp.num_pages)
        last_page = ppp.page_range[len(ppp.page_range) - 1]
        page_set = get_pageset(last_page, page)
        t = get_template('search_result_single_m.html')
        form = SearchForm()
        content_html = t.render(
            RequestContext(request, {'form':form,'results': results, 'last_page': last_page, 'page_set': page_set,'params':request.GET.get('params')}))
        payload = {
            'content_html': content_html,
            'success': True
        }
        return HttpResponse(json.dumps(payload), content_type="application/json")

    elif request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            amount = cd['searchWord']

            try:
                page = int(request.GET.get('page', '1'))
            except ValueError:
                page = 1
            a = [1,7,13,16,22,28,36]
            sorttype = 0
            sortorder = 0

            if amount:
                try :
                    int(amount)
                    results = Bid.objects.filter(amount__gte=amount).order_by("random_rank").order_by("amount")
                except ValueError:
                    results = Bid.objects.all().order_by("random_rank").order_by("amount")
            else:
                results = Bid.objects.all().order_by("random_rank").order_by("amount")
            filters = DimensionChoice.objects.filter(id__in=a)
            results = data_filter(results, filters)
            if sorttype is not None and sortorder is not None:
                results = result_sort(results, sorttype, sortorder)
            ppp = Paginator(results, 3)

            try:
                page = int(request.POST.get('page', '1'))
            except ValueError:
                page = 1
            try:
                results = ppp.page(page)
            except (EmptyPage, InvalidPage):
                results = ppp.page(ppp.num_pages)
            last_page = ppp.page_range[len(ppp.page_range) - 1]
            page_set = get_pageset(last_page, page)

            return render_to_response('search_result_m.html',
                                      {'params':a,'amount':amount,'results': results, 'last_page': last_page,'page_set': page_set,'form':form},
                                      context_instance=RequestContext(request))
    else:
        form = SearchForm()
        return render_to_response('detail_search_m.html',{'form':form}, context_instance=RequestContext(request))

def agreement(request):
    return render_to_response('agreement_m.html',{}, context_instance=RequestContext(request))