#-*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from webgui.models import Webradio, Player, Alarmclock, BackupMP3
from webgui.forms import WebradioForm, AlarmClockForm, BackupMP3Form
import os, glob
import subprocess
from time import strftime
import time
import urllib
from utils.AudioManager import AudioManager


def homepage(request):
    try:
        radio = Webradio.objects.get(selected=1)
    except Webradio.DoesNotExist:
        radio = None
    player = Player()
    listalarmclock = Alarmclock.objects.all()
    # clock
    clock = strftime("%H:%M:%S")
    # get sound info
    am = AudioManager()
    currentvolume = am.get_percent_volume()
    currentmute = am.get_mute_status()
    return render(request, 'homepage.html', {'radio': radio,
                                             'player': player,
                                             'listalarmclock': listalarmclock,
                                             'clock': clock,
                                             'currentVolume': currentvolume,
                                             'currentMute': currentmute})

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
    # get sound info
    am = AudioManager()
    current_volume = am.get_percent_volume()
    current_mute = am.get_mute_status()

    # get actual mp3 backup file
    actual_backup = _get_mp3_in_backup_folder()

    if request.method == 'POST':
        form = BackupMP3Form(request.POST, request.FILES)
        if form.is_valid():
            # remove backup save in database
            BackupMP3.objects.all().delete()
            # remove file in backup folder
            _delete_mp3_from_backup_folder()
            form.save()
            return redirect('webgui.views.options')
    else:
        form = BackupMP3Form()

    return render(request, 'options.html', {'currentVolume': current_volume,
                                            'currentMute': current_mute,
                                            'form': form,
                                            'backup': actual_backup})


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
        os.system("gpio mode 0 out")
        os.system("gpio write 0 1")
    else:
        # play backup MP3
        radio.url = 'mplayer backup_mp3/*'
        player.play(radio)

    return redirect('webgui.views.homepage')

def stop(request):
    player = Player()
    player.stop()
    os.system("gpio mode 0 out")
    os.system("gpio write 0 0")
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
            period_crontab = _convert_period_to_crontab(period)
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
    am = AudioManager()
    am.volume_up()
    return redirect('webgui.views.homepage')


def volumedown(request, count):
    am = AudioManager()
    am.volume_down()
    return redirect('webgui.views.homepage')


def volumeset(request, volume):
    am = AudioManager()
    am.set_volume(int(volume))
    return redirect('webgui.views.homepage')


def volumetmute(request):
    am = AudioManager()
    am.togglemute()
    return redirect('webgui.views.homepage')


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


def _get_mp3_in_backup_folder():
    path = os.path.dirname(os.path.abspath(__file__))+"/../backup_mp3"
    mp3 = os.listdir(path)
    if mp3:
        return mp3[0]

def _delete_mp3_from_backup_folder():
    path = os.path.dirname(os.path.abspath(__file__))+"/../backup_mp3/*"
    filelist = glob.glob(path)
    for f in filelist:
        os.remove(f)
