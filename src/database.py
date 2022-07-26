from fastapi import HTTPException
from pymongo import MongoClient
from src.models import NoteResult
from datetime import datetime
from src.util import hashpass, verify
from pymongo.errors import DuplicateKeyError
from pymongo.cursor import Cursor
from dotenv import find_dotenv, load_dotenv
import os

load_dotenv(find_dotenv())

mongo = MongoClient(
    host=os.getenv('DATABASE_URL'), username=os.getenv('DATABASE_USERNAME'), password=os.getenv('DATABASE_PASSWORD'))

database = mongo['newnotes']

notes_collection = database['notes']
users_collection = database['users']
users_collection.create_index('email', unique=True)


async def db_parser(cursor: Cursor):
    ''' parse data from database into lists '''
    notes = []
    for doc in cursor:
        notes.append(
            NoteResult(**doc))
    return notes


async def fetch_all(current_user: dict, limit: int, skip: int, title: str):
    ''' fetch every note from owner '''
    if current_user['role'] == 'user':
        cursor = notes_collection.find(
            {'title': {"$regex": title},'owner':current_user['email']}).limit(limit).skip(skip)
        result = await db_parser(cursor)
        return result
    cursor = notes_collection.find(
        {'title': {"$regex": title}}).limit(limit).skip(skip)
    result = await db_parser(cursor)
    return result


async def update_note(title: str, description: str, current_user: str):
    ''' update note '''
    notes_collection.update_one({'title': title, 'owner': current_user['email']}, {
                                "$set": {"description": description}})
    return notes_collection.find_one({"title": title})


async def remove_note(title: str, current_user: dict):
    ''' remove note '''
    find = notes_collection.delete_one({"title": title, 'owner': current_user['email']})
    if find:
        return True
    raise HTTPException(404, "Item not found")


async def create_note(note: dict, current_user: str):
    ''' create note '''
    note['created_at'] = datetime.now()
    note['owner'] = current_user['email']
    print(note)
    notes_collection.insert_one(note)
    return note


async def create_user(user: dict, current_user: str):
    ''' create user '''

    if user['role'] == 'super_admin' and current_user == 'admin':
        raise HTTPException(404, f'you do not have access you are a admin')

    user['password'] = hashpass(user['password'])
    user['created_at'] = datetime.now()
    try:
        users_collection.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(404, 'User already exist')
    return user


async def find_user(email: str):
    ''' find user '''
    return users_collection.find_one({"email": email})


async def change_user_password(passwords: dict, current_user: dict):
    ''' change user password '''
    find = users_collection.find_one({"email": current_user['email']})
    if find:
        if verify(passwords['old_password'], find['password']):
            new_pass = hashpass(passwords['new_password'])
            users_collection.update_one({"email": current_user}, {
                                        '$set': {'password': new_pass}})
            return "Password Updated"
        raise HTTPException(404, "Wrong Old Password")
    return None


async def delete_user(email: str):
    ''' delete user '''
    find = users_collection.find_one({'email': email})
    if find:
        users_collection.delete_one({"email": email})
        notes_collection.delete_many({"owner": email})
        return "User gone"
    raise HTTPException("User Not Found")
