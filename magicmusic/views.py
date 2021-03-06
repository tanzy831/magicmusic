# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse, Http404

from magicmusic.models import *
from magicmusic.forms import *
from magicmusic.midilib import MidiLib
from community.models import *
from community.forms import *

import json

@login_required
def mymusic(request):
    if request.method == 'GET':
        objects = Workspace.objects.filter(
            workspace_group__users__in=[request.user])
        workspaces = []
        for e in objects:
            workspace = []
            workspace = {'name': e.name, 'id': e.id}
            workspaces.append(workspace)
        context = {'workspaces': workspaces}
        return render(request, 'magicmusic/mymusic.html', context)
    else:
        print("post\n")


@login_required
def addworkspace(request):
    # print("addworkspace\n")
    if request.method == 'GET':
        context = {'form': WorkspaceForm()}
        return render(request, 'magicmusic/addworkspace.html', context)
    else:
        newworkspace_form = WorkspaceForm(request.POST)
        with transaction.atomic():
            newworkspacegroup = WorkspaceGroup()
            newworkspacegroup.save()
            # print("newworkspacegroup id: " + str(newworkspacegroup.id))
            newworkspacegroup.users.add(request.user)
            # print("newworkspacegroup user: " + str(newworkspacegroup.users.all()[0]))
            newworkspacegroup.save()
        newworkspace = Workspace(workspace_group=newworkspacegroup,
                                 name=newworkspace_form.data['name'],
                                 description=newworkspace_form.data['description'],
                                 )
        newworkspace.save()
        # print("newworkspace user: " + str(newworkspace.name))
        return redirect(reverse('mymusic'))


@login_required
def addsong(request, id):
    print("enter addsong")
    if request.method == 'GET':
        context = {'form': SongForm(),  'workspaceID': id}
        return render(request, 'magicmusic/addsong.html', context)
    else:
        context = {}

        with transaction.atomic():
            objects = Workspace.objects.filter(id__exact=id)
            workspace = objects.all()[0]
            new_song = Song(songfile="",
                            creator=request.user.profile,
                            workspace=workspace)
            new_song.save()
            newsong_form = SongForm(request.POST, request.FILES, instance=new_song)
            newsong_form.save()

            new_song_id = new_song.id
            print("new_song_id=", new_song_id)


        # gen new wav and get url
        all_tracks = Track.objects.filter(workspace__id=id)
        track_info_list = []
        for i, tk in enumerate(all_tracks):
            info = {}
            info['channel'] = i
            info['instrument'] = tk.instrument
            info['blob'] = tk.blob
            track_info_list.append(info)

        global_metadata = {}
        filename = "usr_" + str(request.user.id) + \
                   "_song_" + str(new_song_id)
        new_song_path = MidiLib.save_all_track_to_wav(filename, global_metadata, track_info_list, True)

        new_song_path = new_song_path.replace('media/', '', 1)

        new_song_update = Song.objects.filter(id__exact=new_song_id)
        new_song_update.update(songfile=new_song_path)


        return redirect(reverse('mymusic'))

@login_required
def workspace(request, id):
    if request.method == 'GET':
        objects = Workspace.objects.filter(id__exact=id)
        workspace = objects.all()[0]
        # print("workspace is:"+str(workspace.id))
        tracks = []
        objects = Track.objects.filter(workspace__exact=workspace)
        for e in objects:
            track = {'instrument': e.instrument, 'trackid': e.id}
            # print("track instrument is:"+str(e.id))
            tracks.append(track)
        context = {'tracks': tracks, 'workspaceID': id}
        return render(request, 'magicmusic/workspace.html', context)
    else:
        objects = Workspace.objects.filter(id__exact=id)
        workspace = objects.all()[0]
        instrument = request.POST.getlist('instruments')[0]
        newtrack = Track(workspace=workspace,
                         name=request.POST.get('name'),
                         description=request.POST.get('description'),
                         instrument=instrument)
        newtrack.save()
        workspace.track_set.add(newtrack)
        workspace.save()
        tracks = []
        objects = Track.objects.filter(workspace__exact=workspace)
        for e in objects:
            track = {'instrument': e.instrument, 'trackid': e.id, 'name':e.name, 'description':e.description}
            tracks.append(track);
        context = {'tracks': tracks, 'workspaceID': id}
        return render(request, 'magicmusic/workspace.html', context)


@login_required
def track(request, id):
    if request.method == 'GET':
        objects = Track.objects.filter(id__exact=id)
        track = objects.all()[0]
        instrument_name = track.instrument

        unit_note_urls = MidiLib.generate_unit_notes_if_not_exists(instrument_name)
        # # trim the url and no "media/" at begin"
        unit_note_urls_trimmed = []
        for uri in unit_note_urls:
            trim = uri.replace('media/', '', 1)
            unit_note_urls_trimmed.append(trim)

        json_blob = Track.objects.filter(id__exact=id).values('blob')[0]["blob"]
        if json_blob == None:
            blob_json = ""
        else:
            blob_json = json.loads(str(json_blob))["blob"]

        context = {'trackID': id,
                   'notes_blob': blob_json,
                   'unit_note_urls': unit_note_urls_trimmed}

        return render(request, 'magicmusic/track.html', context)
    else:
        print("post")


@login_required
def profile(request):
    print("profile")


@login_required
def follower(request):
    print("follower")


@login_required
def generate_music(request, trackID):
    if not request.POST:
        raise Http404
    else:
        if 'notes_blob' not in request.POST or \
                not request.POST['notes_blob']:
            json_error = \
                '{"error": "You should pass some musical blob data to backend."}'
            return HttpResponse(json_error, content_type='application/json')
        else:

            notes_blob = request.POST['notes_blob']

            channel = 0
            time_multiplier = 96
            global_metadata = {}
            track_metadata = {}
            sorted_commands = MidiLib.parse_midi_offset_from_blob(notes_blob)

            formatted_onoffs = MidiLib.format_mido_onoffs_default_velocity(
                offset_note_messages=sorted_commands, channel=channel,
                multiplier=time_multiplier)

            track_qs = Track.objects.filter(id__exact=trackID)
            track = track_qs[0]
            workspace = track.workspace
            all_tracks = Track.objects.filter(workspace__id=workspace.id)
            # channel = 0
            # for i, potential_track in enumerate(all_tracks):
            #     if potential_track.id == track.id:
            #         channel = i

            track_metadata["instrument"] = track.instrument
            # track_metadata["channel"] = channel

            filename = "usr_"+ str(request.user.id) + \
                       "_ws_" + str(workspace.id) +"_trk_" + str(track.id)
            file_path = MidiLib.save_one_track_to_wav(filename, global_metadata, track_metadata, formatted_onoffs)


            # update database with the new notes blob
            blob_json = {"blob": notes_blob}

            track_qs.update(blob=json.dumps(blob_json))


            res_obj = {
                'file_path': file_path
            }
            res_str = json.dumps(res_obj)

            return HttpResponse(res_str, content_type='application/json')

@login_required
def generate_workspace_music(request, workspace_id):
    if not request.POST:
        raise Http404
    else:
        # TODO: no tracks in workspace

        all_tracks = Track.objects.filter(workspace__id=workspace_id)
        track_info_list = []
        for i, tk in enumerate(all_tracks):
            info = {}
            info['channel'] = i
            info['instrument'] = tk.instrument
            info['blob'] = tk.blob
            track_info_list.append(info)

        global_metadata={}
        filename = "usr_" + str(request.user.id) + \
                   "_ws_" + str(workspace_id)
        file_path = MidiLib.save_all_track_to_wav(filename, global_metadata, track_info_list, False)

        res_obj = {
            'file_path': file_path
        }
        res_str = json.dumps(res_obj)

        return HttpResponse(res_str, content_type='application/json')
