#-*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from webgui.models import Webradio, Player, Alarmclock
from webgui.forms import WebradioForm, AlarmClockForm
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
import os
import subprocess
from time import strftime
import time
import urllib
import requests
from contextlib import closing


def homepage(request):
    try:
        radio = Webradio.objects.get(selected=1)
    except Webradio.DoesNotExist:
        radio = None
    player = Player()
    listalarmclock = Alarmclock.objects.all()
    # clock
    clock = strftime("%H:%M:%S")
    return render(request, 'homepage.html', {'radio': radio,
                                             'player': player,
                                             'listalarmclock': listalarmclock,
                                             'clock': clock})


def webradio(request):
    listradio = Webradio.objects.all()
    return render(request, 'webradio.html', {'listradio': listradio})


def update_webradio(request, id_webradio):
    selected_webradio = get_object_or_404(Webradio, id=id_webradio)
    form = WebradioForm(request.POST or None, instance=selected_webradio)
    if form.is_valid():
        form.save()
        return redirect('webgui.views.webradio')

    return render(request, 'update_webradio.html', {'form': form, 'radio': selected_webradio})


def addwebradio(request):
    if request.method == 'POST':  # If the form has been submitted...
        form = WebradioForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # save web radio
            form.instance.selected = False
            form.save()
            return redirect('webgui.views.webradio')
    else:
        form = WebradioForm()

    return render(request, 'addwebradio.html', {'form': form})


def delete_web_radio(request, id_radio):
    radio = Webradio.objects.get(id=id_radio)
    radio.delete()
    return redirect('webgui.views.webradio')


def options(request):
    script_path = os.path.dirname(os.path.abspath(__file__))+"/utils/picsound.sh"
    current_volume = subprocess.check_output([script_path, "--getLevel"])
    current_mute = subprocess.check_output([script_path, "--getSwitch"])
    return render(request, 'options.html', {'currentVolume': current_volume, 'currentMute': current_mute})


def debug(request):
    todisplay = 'hello world debug'
    return render(request, 'debug.html', {'todisplay': todisplay})


def play(request, id_radio):
    # get actual selected radio if exist
    try:
        selectedradio = Webradio.objects.get(selected=1)
        # unselect it
        selectedradio.selected = False
        selectedradio.save()
    except Webradio.DoesNotExist:
        pass

    # set the new selected radio
    radio = Webradio.objects.get(id=id_radio)
    radio.selected = True
    radio.save()
    player = Player()
    # check if url is available
    try:
        http_code = urllib.urlopen(radio.url).getcode()
    except IOError:
        http_code = 0
    print http_code
    if http_code == 200:
        player.play(radio)
    else:
        # play backup MP3
        radio.url = 'mplayer -loop 0 backup.mp3'
        player.play(radio)

    return redirect('webgui.views.homepage')

def stop(request):
    player = Player()
    player.stop()
    time.sleep(1)
    return redirect('webgui.views.homepage')


def alarmclock(request):
    list_alarm = Alarmclock.objects.all()
    return render(request, 'alarmclock.html', {'listAlarm': list_alarm})


def activeAlarmClock(request, id):
    alarmclock = Alarmclock.objects.get(id=id)
    if not alarmclock.active:
        alarmclock.active = True
        alarmclock.enable()
    else:
        alarmclock.active = False
        alarmclock.disable()

    alarmclock.save()
    return redirect('webgui.views.alarmclock')


def create_alarmclock(request):
    if request.method == 'POST':
        form = AlarmClockForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # convert period
            period = form.cleaned_data['period']
            period_crontab = _convert_period_to_crontab()
            form.period = _convert_period_to_crontab(period)
            # save in database
            form.save()
            # set the cron
            alarmclock = Alarmclock.objects.latest('id')
            alarmclock.period = period_crontab
            alarmclock.active = True
            alarmclock.enable()
            alarmclock.save()

            return redirect('webgui.views.alarmclock')
    else:
        form = AlarmClockForm()  # An unbound form
    return render(request, 'create_alarmclock.html', {'form': form})


def update_alarmclock(request, id_alarmclock):
    selected_webradio = get_object_or_404(Alarmclock, id=id_alarmclock)
    form = AlarmClockForm(request.POST or None, instance=selected_webradio)
    if form.is_valid():
        # convert period
        period = form.cleaned_data['period']
        period_crontab = _convert_period_to_crontab(period)
        form.period = period_crontab
        # save in database
        form.save()
        # set the cron
        alarmclock = Alarmclock.objects.latest('id')
        alarmclock.period = period_crontab
        # disble to remove from crontab
        alarmclock.disable()
        # then enable to create it again
        alarmclock.enable()
        alarmclock.save()

        return redirect('webgui.views.alarmclock')

    return render(request, 'update_alarmclock.html', {'form': form, 'alarmclock': selected_webradio})


def deleteAlarmClock(request, id_alarmclock):
    target_alarmclock = Alarmclock.objects.get(id=id_alarmclock)
    target_alarmclock.disable()
    target_alarmclock.delete()
    return redirect('webgui.views.alarmclock')


def volumeup(request, count):
    script_path = os.path.dirname(os.path.abspath(__file__))+"/utils/picsound.sh"
    subprocess.call([script_path, "--up", count])
    return redirect('webgui.views.options')


def volumedown(request, count):
    script_path = os.path.dirname(os.path.abspath(__file__))+"/utils/picsound.sh"
    subprocess.call([script_path, "--down", count])
    return redirect('webgui.views.options')


def volumeset(request, volume):
    script_path = os.path.dirname(os.path.abspath(__file__))+"/utils/picsound.sh"
    subprocess.call([script_path, "--setLevel", volume])
    return redirect('webgui.views.options')


def volumetmute(request):
    script_path = os.path.dirname(os.path.abspath(__file__))+"/utils/picsound.sh"
    subprocess.call([script_path, "--toggleSwitch"])
    return redirect('webgui.views.options')


def _convert_period_to_crontab(period):
    # decode unicode
    period_decoded = [str(x) for x in period]

    # transform period into crontab compatible
    period_crontab = ""
    first_time = True  # first time we add a value
    for p in period_decoded:
        if first_time:  # we do not add ","
            period_crontab += str(p)
            first_time = False
        else:
            period_crontab += ","
            period_crontab += str(p)
    return period_crontab