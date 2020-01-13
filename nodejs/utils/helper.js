'user strict';

const DB = require('./db');
const path = require('path');
const fs = require('fs');

class Helper{

	constructor(app){
		this.db = DB;
	}

	async addSocketId(userId, userSocketId){
		try {
			return await this.db.query(`UPDATE users SET socket_id = $1, online= $2 WHERE id = $3`, [userSocketId,'Y',userId]);
		} catch (error) {
			// console.log("HI");
			// console.log(error);
			return null;
		}
	}

	async logoutUser(userSocketId){
		return await this.db.query(`UPDATE users SET socket_id = $1, online= $2 WHERE socket_id = $3`, ['','N',userSocketId]);
	}
	async getUser(userSocketId){
        try {
            return Promise.all([
                this.db.query(`SELECT * FROM users where socket_id=$1`, [userSocketId])
            ]).then( (response) => {
                if (response[0].rows.length > 0)
                    return response[0].rows[0];
                else {
                    return null;
                }
            }).catch( (error) => {
                console.warn(error);
                return (null);
            });
        } catch (error) {
            console.warn(error);
            return null;
        }
	}

	getChatList(userId){
		try {
            return Promise.all([
				this.db.query(`SELECT id, first_name, last_name, socket_id, online, updated_at FROM users WHERE id != $1`, [userId])
			]).then( (response) => {
                return {
					chatlist : response[0].rows
				};
			}).catch( (error) => {
				console.warn(error);
				return (null);
			});
		} catch (error) {
            console.warn(error);
			return null;
		}
	}

	async insertMessages(params){
		try {
			return await this.db.query("INSERT INTO messages (`type`, `file_format`, `file_path`, `from_user_id`,`to_user_id`,`message`, `date`, `time`, `ip`) values ($1,$2,$3,$4,$5,$6,$7,$8,$9)", [params.type, params.fileFormat, params.filePath, params.fromUserId, params.toUserId, params.message, params.date, params.time,params.ip]
			);
		} catch (error) {
			console.warn(error);
			return null;
		}
	}

	async getMessages(userId, toUserId){
		try {
			return await this.db.query(
				`SELECT id,from_user_id as fromUserId,to_user_id as toUserId,message,time,date,type,file_format as fileFormat,file_path as filePath FROM messages WHERE
					(from_user_id = $1 AND to_user_id = $2 )
					OR
					(from_user_id = $1 AND to_user_id = $2 )	ORDER BY id ASC
				`,
				[userId, toUserId, toUserId, userId]
			);
		} catch (error) {
			console.warn(error);
			return null;
		}
	}

	async mkdirSyncRecursive(directory){
		var dir = directory.replace(/\/$/, '').split('/');
        for (var i = 1; i <= dir.length; i++) {
            var segment = path.basename('uploads') + "/" + dir.slice(0, i).join('/');
            !fs.existsSync(segment) ? fs.mkdirSync(segment) : null ;
        }
	}
}
module.exports = new Helper();
