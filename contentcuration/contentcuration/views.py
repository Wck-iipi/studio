import copy
import json
import logging
import os
import urlparse
import zlib
import re
import tempfile
import shutil
from rest_framework import status
from cStringIO import StringIO
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView
from django.shortcuts import render, get_object_or_404, redirect, render_to_response
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core import paginator
from django.core.management import call_command
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import get_storage_class
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.context_processors import csrf
from django.db.models import Q
from django.template import RequestContext
from django.template.loader import render_to_string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from contentcuration.models import Exercise, AssessmentItem, Channel, License, FileFormat, File, FormatPreset, ContentKind, ContentNode, ContentTag, User, Invitation, generate_file_on_disk_name
from contentcuration.forms import InvitationForm, InvitationAcceptForm, RegistrationForm
from contentcuration.api import get_file_diff, api_create_channel
from registration.backends.hmac.views import RegistrationView
from contentcuration.serializers import ExerciseSerializer, ChannelListSerializer, AssessmentItemSerializer, ChannelSerializer, LicenseSerializer, FileFormatSerializer, FormatPresetSerializer, ContentKindSerializer, ContentNodeSerializer, TagSerializer, UserSerializer
from django.core.cache import cache
from le_utils.constants import format_presets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication

def base(request):
    if request.user.is_authenticated():
        return redirect('channels')
    else:
        return redirect('accounts/login')

def testpage(request):
    return render(request, 'test.html')

@login_required
@authentication_classes((SessionAuthentication, BasicAuthentication, TokenAuthentication))
@permission_classes((IsAuthenticated,))
def channel_list(request):
    channel_list = Channel.objects.filter(deleted=False, editors__email__contains= request.user)
    channel_list = ChannelListSerializer.setup_eager_loading(channel_list)
    channel_serializer = ChannelListSerializer(channel_list, many=True)

    licenses = get_or_set_cached_constants(License, LicenseSerializer)
    return render(request, 'channel_list.html', {"channels" : JSONRenderer().render(channel_serializer.data),
                                                 "license_list" : licenses,
                                                 "channel_list" : channel_list.values("id", "name"),
                                                 "current_user" : JSONRenderer().render(UserSerializer(request.user).data)})

@login_required
@authentication_classes((SessionAuthentication, BasicAuthentication, TokenAuthentication))
@permission_classes((IsAuthenticated,))
def channel(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id, deleted=False)
    channel_serializer =  ChannelSerializer(channel)

    accessible_channel_list = Channel.objects.filter( Q(deleted=False, public=True) | Q(deleted=False, editors__email__contains= request.user))
    accessible_channel_list = ChannelListSerializer.setup_eager_loading(accessible_channel_list)
    accessible_channel_list_serializer = ChannelListSerializer(accessible_channel_list, many=True)

    channel_list = accessible_channel_list.filter(editors__email__contains= request.user).exclude(id=channel_id).values("id", "name")
    fileformats = get_or_set_cached_constants(FileFormat, FileFormatSerializer)
    licenses = get_or_set_cached_constants(License, LicenseSerializer)
    formatpresets = get_or_set_cached_constants(FormatPreset, FormatPresetSerializer)
    contentkinds = get_or_set_cached_constants(ContentKind, ContentKindSerializer)

    channel_tags = ContentTag.objects.filter(channel = channel)
    channel_tags_serializer = TagSerializer(channel_tags, many=True)

    json_renderer = JSONRenderer()

    return render(request, 'channel_edit.html', {"channel" : json_renderer.render(channel_serializer.data),
                                                "channel_id" : channel_id,
                                                "channel_name": channel.name,
                                                "accessible_channels" : json_renderer.render(accessible_channel_list_serializer.data),
                                                "channel_list" : channel_list,
                                                "fileformat_list" : fileformats,
                                                 "license_list" : licenses,
                                                 "fpreset_list" : formatpresets,
                                                 "ckinds_list" : contentkinds,
                                                 "ctags": json_renderer.render(channel_tags_serializer.data),
                                                 "current_user" : json_renderer.render(UserSerializer(request.user).data)})

def get_or_set_cached_constants(constant, serializer):
    cached_data = cache.get(constant.__name__)
    if cached_data is not None:
        return cached_data
    constant_objects = constant.objects.all()
    constant_serializer = serializer(constant_objects, many=True)
    constant_data = JSONRenderer().render(constant_serializer.data)
    cache.set(constant.__name__, constant_data, None)
    return constant_data

def exercise_list(request):

    exercise_list = Exercise.objects.all().order_by('title')

    paged_list = paginator.Paginator(exercise_list, 25)  # Show 25 exercises per page

    page = request.GET.get('page')

    try:
        exercises = paged_list.page(page)
    except paginator.PageNotAnInteger:
        # If page is not an integer, deliver first page.
        exercises = paged_list.page(1)
    except paginator.EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        exercises = paged_list.page(paginator.num_pages)

    serializer = ExerciseSerializer(exercises.object_list, many=True)

    return render(request, 'exercise_list.html', {"exercises": exercises, "blob": JSONRenderer().render(serializer.data)})


def exercise(request, exercise_id):

    exercise = get_object_or_404(Exercise, id=exercise_id)

    serializer = ExerciseSerializer(exercise)

    assessment_items = AssessmentItem.objects.filter(exercise=exercise)

    assessment_serialize = AssessmentItemSerializer(assessment_items, many=True)

    return render(request, 'exercise_edit.html', {"exercise": JSONRenderer().render(serializer.data), "assessment_items": JSONRenderer().render(assessment_serialize.data)})

# TODO-BLOCKER: remove this csrf_exempt! People might upload random stuff here and we don't want that.
@csrf_exempt
def file_upload(request):
    if request.method == 'POST':
        preset = FormatPreset.objects.get(id=request.META.get('HTTP_PRESET'))
        #Implement logic for switching out files without saving it yet
        ext = os.path.splitext(request.FILES.values()[0]._name)[1].split(".")[-1]
        original_filename = request.FILES.values()[0]._name
        size = request.FILES.values()[0]._size
        file_object = File(file_size=size, file_on_disk=request.FILES.values()[0], file_format=FileFormat.objects.get(extension=ext), original_filename = original_filename, preset=preset)
        file_object.save()
        return HttpResponse(json.dumps({
            "success": True,
            "filename": str(file_object),
            "object_id": file_object.pk
        }))

def file_create(request):
    if request.method == 'POST':
        ext = os.path.splitext(request.FILES.values()[0]._name)[1].split(".")[-1]
        size = request.FILES.values()[0]._size
        kind = FormatPreset.objects.filter(allowed_formats__extension__contains=ext).first().kind
        original_filename = request.FILES.values()[0]._name
        new_node = ContentNode(title=original_filename.split(".")[0], kind=kind, license_id=settings.DEFAULT_LICENSE, author=request.user.get_full_name())
        new_node.save()
        file_object = File(file_on_disk=request.FILES.values()[0], file_format=FileFormat.objects.get(extension=ext), original_filename = original_filename, contentnode=new_node, file_size=size)
        file_object.save()

        return HttpResponse(json.dumps({
            "success": True,
            "object_id": new_node.pk
        }))

# TODO-BLOCKER: remove this csrf_exempt! People might upload random stuff here and we don't want that.
@csrf_exempt
def file_diff(request):
    logging.debug("Entering the file_diff endpoint")
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST requests are allowed on this endpoint.")
    else:
        data = json.loads(request.body)
        return HttpResponse(json.dumps(get_file_diff(data)))

# TODO-BLOCKER: remove this csrf_exempt! People might upload random stuff here and we don't want that.
@csrf_exempt
def api_file_upload(request):
    if request.method != 'POST':
        raise HttpResponseBadRequest("Only POST requests are allowed on this endpoint.")
    else:
        try:
            fobj = request.FILES["file"]
            file_path = generate_file_on_disk_name(fobj._name.split(".")[-2], fobj._name)

            # Write file if it doesn't already exist
            if not os.path.isfile(file_path):
                with open(file_path, 'wb') as destf:
                    shutil.copyfileobj(fobj, destf)

            return HttpResponse(json.dumps({
                "success": True,
            }))
        except KeyError:
            raise ObjectDoesNotExist("Missing attribute from data")

# TODO-BLOCKER: remove this csrf_exempt! People might upload random stuff here and we don't want that.
@csrf_exempt
def api_create_channel_endpoint(request):
    if request.method != 'POST':
        raise HttpResponseBadRequest("Only POST requests are allowed on this endpoint.")
    else:
        data = json.loads(request.body)
        try:
            content_data = data['content_data']
            channel_data = data['channel_data']
            file_data = data['file_data']

            obj = api_create_channel(channel_data, content_data, file_data)
            invitation = Invitation.objects.create(channel=obj)

            return HttpResponse(json.dumps({
                "success": True,
                "new_channel": obj.pk,
                "invite_id":invitation.pk,
            }))
        except KeyError:
            raise ObjectDoesNotExist("Missing attribute from data: {}".format(data))

@login_required
def api_open_channel(request, invitation_id, channel_id):
    if Invitation.objects.filter(id=invitation_id, channel_id=channel_id).exists():
        channel = Channel.objects.get(id=channel_id)
        if not channel.editors.filter(id = request.user.pk).exists():
            channel.editors.add(request.user)
        channel.save()
        Invitation.objects.get(id=invitation_id).delete()
        return redirect('/channels/{0}/edit'.format(channel_id))
    else:
        return redirect('/open_fail')

def fail_open_channel(request):
    return render(request, 'permissions/open_channel_fail.html')

@csrf_exempt
def thumbnail_upload(request):
    if request.method == 'POST':
        filename = request.FILES.values()[0]._name
        ext = os.path.splitext(filename)[1].split(".")[-1] # gets file extension without leading period
        file_object = File(file_on_disk=request.FILES.values()[0], file_format_id=ext, preset_id=format_presets.CHANNEL_THUMBNAIL)
        file_object.save()
        return HttpResponse(json.dumps({
            "success": True,
            "filename": "{0}.{ext}".format(file_object.checksum, ext=ext),
        }))

def exercise_image_upload(request):

    if request.method == 'POST':
        node = ContentNode.objects.get(id=request.META.get('HTTP_NODE'))
        ext = os.path.splitext(request.FILES.values()[0]._name)[1].split(".")[-1] # gets file extension without leading period
        file_object = File(file_on_disk=request.FILES.values()[0], file_format=FileFormat.objects.get(extension=ext), contentnode=node)
        file_object.save()
        return HttpResponse(json.dumps({
            "success": True,
            "filename": file_object.file_on_disk.url,
        }))

def duplicate_nodes(request):
    logging.debug("Entering the copy_node endpoint")

    if request.method != 'POST':
        raise HttpResponseBadRequest("Only POST requests are allowed on this endpoint.")
    else:
        data = json.loads(request.body)

        try:
            node_ids = data["node_ids"]
            sort_order = data["sort_order"]
            target_parent = data["target_parent"]
        except KeyError:
            raise ObjectDoesNotExist("Missing attribute from data: {}".format(data))

        logging.info("Copying node id %s", node_ids)

        nodes = node_ids.split()
        new_nodes = []

        for node_id in nodes:
            new_node = _duplicate_node(node_id, sort_order=sort_order, parent=target_parent)
            new_nodes.append(new_node.pk)
            sort_order+=1

        return HttpResponse(json.dumps({
            "success": True,
            "node_ids": " ".join(new_nodes)
        }))

def _duplicate_node(node, sort_order=1, parent=None):
    if isinstance(node, int) or isinstance(node, basestring):
        node = ContentNode.objects.get(pk=node)
    new_node = ContentNode.objects.create(
        title=node.title,
        description=node.description,
        kind=node.kind,
        license=node.license,
        parent=ContentNode.objects.get(pk=parent) if parent else None,
        sort_order=sort_order,
        copyright_holder=node.copyright_holder,
        changed=True,
        original_node=node.original_node or node,
        cloned_source=node,
        author=node.author,
        content_id=node.content_id,
        extra_fields=node.extra_fields,
    )

    # add tags now
    new_node.tags.add(*node.tags.all())

    # copy file object too
    for fobj in node.files.all():
        fobj_copy = copy.copy(fobj)
        fobj_copy.id = None
        fobj_copy.contentnode = new_node
        fobj_copy.save()

    # copy assessment item object too
    for aiobj in node.assessment_items.all():
        aiobj_copy = copy.copy(aiobj)
        aiobj_copy.id = None
        aiobj_copy.contentnode = new_node
        aiobj_copy.save()

    for c in node.children.all():
        _duplicate_node(c, parent=new_node.id)

    return new_node

@csrf_exempt
def publish_channel(request):
    logging.debug("Entering the publish_channel endpoint")
    if request.method != 'POST':
        raise HttpResponseBadRequest("Only POST requests are allowed on this endpoint.")
    else:
        data = json.loads(request.body)

        try:
            channel_id = data["channel_id"]
        except KeyError:
            raise ObjectDoesNotExist("Missing attribute from data: {}".format(data))

        call_command("exportchannel", channel_id)

        return HttpResponse(json.dumps({
            "success": True,
            "channel": channel_id
        }))

""" REGISTRATION/INVITATION ENDPOINTS """
@csrf_exempt
def send_invitation_email(request):
    if request.method != 'POST':
        raise HttpResponseBadRequest("Only POST requests are allowed on this endpoint.")
    else:
        data = json.loads(request.body)

        try:
            user_email = data["user_email"]
            channel_id = data["channel_id"]
            retrieved_user = User.objects.get_or_create(email = user_email)
            recipient = retrieved_user[0]
            channel = Channel.objects.get(id=channel_id)
            invitation = Invitation.objects.get_or_create(invited = recipient,
                                                        email = user_email,
                                                        sender=request.user,
                                                        channel_id = channel_id,
                                                        first_name=recipient.first_name if recipient.is_active else "Guest",
                                                        last_name=recipient.last_name if recipient.is_active else " ")[0]
            ctx_dict = {    'sender' : request.user,
                            'site' : get_current_site(request),
                            'user' : recipient,
                            'channel_id' : channel_id,
                            'invitation_key': invitation.id,
                            'is_new': recipient.is_active is False,
                            'channel': channel.name
                        }
            subject = render_to_string('permissions/permissions_email_subject.txt', ctx_dict)
            message = render_to_string('permissions/permissions_email.txt', ctx_dict)
            # message_html = render_to_string('permissions/permissions_email.html', ctx_dict)
            recipient.email_user(subject, message, settings.DEFAULT_FROM_EMAIL,) #html_message=message_html,)
            # recipient.email_user(subject, message, settings.DEFAULT_FROM_EMAIL,)
        except KeyError:
            raise ObjectDoesNotExist("Missing attribute from data: {}".format(data))

        return HttpResponse(json.dumps({
                "id": invitation.pk,
                "invited": invitation.invited_id,
                "email": invitation.email,
                "sender": invitation.sender_id,
                "channel": invitation.channel_id,
                "first_name": invitation.first_name,
                "last_name": invitation.last_name,
            }))

class InvitationAcceptView(FormView):
    form_class = InvitationAcceptForm
    template_name = 'permissions/permissions_confirm.html'
    invitation = None

    # def get_initial(self):
    #     initial = self.initial.copy()
    #     return {'userid': self.kwargs["user_id"]}

    def get_form_kwargs(self):
        kwargs = super(InvitationAcceptView, self).get_form_kwargs()
        kwargs.update({'user': self.user()})
        return kwargs

    def get_success_url(self):
        return "/channels/" + self.kwargs["channel_id"] + "/edit"

    def dispatch(self, *args, **kwargs):
        user = self.user()
        try:
            self.invitation = Invitation.objects.get(id = self.kwargs['invitation_link'])
        except ObjectDoesNotExist:
            logging.debug("No invitation found.")
            channel = Channel.objects.get(id=self.kwargs["channel_id"])
            if user in channel.editors.all():
                return super(InvitationAcceptView, self).dispatch(*args, **kwargs)
            return redirect("/invitation_fail")

        return super(InvitationAcceptView, self).dispatch(*args, **kwargs)

    def user(self):
        return User.objects.get_or_create(id=self.kwargs["user_id"])[0]

    def form_valid(self, form):
        channel = Channel.objects.get(id=self.kwargs["channel_id"])
        user = self.user()
        if user not in channel.editors.all():
            channel.editors.add(user)
            channel.save()
            if self.invitation is not None:
                self.invitation.delete()

        user_cache = authenticate(username=user.email,
                            password=form.cleaned_data['password'],
                        )
        login(self.request, user_cache)

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        return super(InvitationAcceptView, self).get_context_data(**kwargs)


class InvitationRegisterView(FormView):
    """
    Base class for user registration views.
    """
    disallowed_url = 'registration_disallowed'
    form_class = InvitationForm
    success_url = None
    template_name = 'permissions/permissions_register.html'
    invitation = None

    def get_initial(self):
        initial = self.initial.copy()
        return {'email': self.user().email}

    def get_success_url(self):
        return "/accept_invitation/" + self.kwargs["user_id"] + "/" + self.kwargs["invitation_link"] + "/" + self.kwargs["channel_id"]

    def get_login_url(self):
        return "/channels/" + self.kwargs["channel_id"] + "/edit"

    def dispatch(self, *args, **kwargs):
        user = self.user()
        try:
            self.invitation = Invitation.objects.get(id__exact = self.kwargs['invitation_link'])
        except ObjectDoesNotExist:
            logging.debug("No invitation found.")
            channel = Channel.objects.get(id=self.kwargs["channel_id"])
            if user in channel.editors.all():
                return redirect(self.get_success_url())
            return redirect("/invitation_fail")

        if not getattr(settings, 'REGISTRATION_OPEN', True):
            return redirect(self.disallowed_url)

        if user.is_active:
            return redirect(self.get_success_url())

        return super(InvitationRegisterView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        user = form.save(self.user())
        channel = Channel.objects.get(id=self.kwargs["channel_id"])
        if user not in channel.editors.all():
            channel.editors.add(user)
            channel.save()
            if self.invitation is not None:
                self.invitation.delete()
        user_cache = authenticate(username=user.email,
                             password=form.cleaned_data['password1'],
                         )
        login(self.request, user_cache)
        return redirect(self.get_login_url())


    def form_invalid(self, form):

        return self.render_to_response(self.get_context_data(form=form))

    def user(self):
        return User.objects.get_or_create(id=self.kwargs["user_id"])[0]

    def get_context_data(self, **kwargs):
        return super(InvitationRegisterView, self).get_context_data(**kwargs)

def decline_invitation(request, invitation_link):
    try:
        invitation = Invitation.objects.get(id = invitation_link)
        invitation.delete()

    except ObjectDoesNotExist:
        logging.debug("No invitation found.")

    return render(request, 'permissions/permissions_decline.html')

def fail_invitation(request):
    return render(request, 'permissions/permissions_fail.html')

class UserRegistrationView(RegistrationView):
    email_body_template = 'registration/activation_email.txt'
    email_subject_template = 'registration/activation_email_subject.txt'
    email_html_template = 'registration/activation_email.html'
    form_class=RegistrationForm

    def send_activation_email(self, user):
        activation_key = self.get_activation_key(user)
        context = self.get_email_context(activation_key)
        context.update({
            'user': user
        })
        subject = render_to_string(self.email_subject_template, context)
        subject = ''.join(subject.splitlines())
        message = render_to_string(self.email_body_template, context)
        # message_html = render_to_string(self.email_html_template, context)
        user.email_user(subject, message, settings.DEFAULT_FROM_EMAIL, ) #html_message=message_html,)
