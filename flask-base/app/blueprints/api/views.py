from datetime import datetime

from flask_login import login_required, current_user
from flask_restful import Resource, Api, reqparse
from sqlalchemy import or_, and_

from app.models import User, Message
from app.utils import db, get_paginated_list, jsonify_object, strip_tags


class PostMessage(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('message', help='This field cannot be blank', required=True)

    @login_required
    def post(self, recipient_id):
        data = self.parser.parse_args()
        user = User.query.filter_by(id=recipient_id).first_or_404()
        msg = Message(user_id=current_user.id, recipient_id=recipient_id,
                      body=strip_tags(data['message']))
        db.session.add(msg)
        db.session.commit()
        db.session.refresh(msg)
        user.add_notification('unread_message_count', user.new_messages())
        return {
            'status': 1,
            'message': jsonify_object(msg)
        }


class GetMessages(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('first_page_last', required=False)

    @login_required
    def get(self, user_id, page_id):
        data = self.parser.parse_args()
        user = User.query.filter_by(id=user_id).first_or_404()
        for message in current_user.history(user.id):
            if message.recipient_id == current_user.id:
                message.read_at = db.func.now()
            db.session.add(message)
        db.session.commit()
        messages = Message.query.order_by(Message.timestamp.desc()). \
            filter(or_(and_(Message.recipient_id == user_id, Message.user_id == current_user.id),
                       and_(Message.recipient_id == current_user.id, Message.user_id == user_id)))
        if data['first_page_last']:
            messages = messages.filter(Message.id <= data['first_page_last'])
        messages = messages.paginate(page_id, per_page=20)
        messages = get_paginated_list(messages)
        return {
            'status': 1,
            'messages': messages,
            'now': str(datetime.now())
        }


main_api = Api()
main_api.add_resource(GetMessages, '/api/messages/<int:user_id>/<int:page_id>')
main_api.add_resource(PostMessage, '/api/messages/<int:recipient_id>')

clients = []

#
# @socket_io.on('message_sent')
# def event(data):
#     message = data['data']
#     client = next((x for x in clients if x['user_id'] == message['recipient_id']), None)
#     room = session.get('room')
#     join_room(room)
#     if client:
#         print("emitting to ", client)
#         emit('message_received', {'message': message}, room=client['sessid'])
#
#
# @socket_io.on('connected')
# def connected():
#     print(session)
#     client = next((x for x in clients if x['user_id'] == current_user.id), None)
#     if client:
#         clients.remove(client)
#     client = {'user_id': current_user.id, 'sessid': request.sid}
#     if client not in clients:
#         clients.append(client)
#     print(clients)
#
#
# @socket_io.on('disconnect')
# def disconnect():
#     client = next((x for x in clients if x['user_id'] == current_user.id), None)
#     if client:
#         clients.remove(client)
#
#
# @socket_io.on('connect')
# def connect_handler():
#     if current_user.is_authenticated:
#         emit('my response',
#              {'message': '{0} has joined'.format(current_user.full_name)},
#              broadcast=True)
#     else:
#         return False  # not allowed here
