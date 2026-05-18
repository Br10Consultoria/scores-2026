import asyncio
from sqlalchemy import desc
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from app.core.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Player, PlayerStats, Team
from app.services.sofascore import sync_teams_and_players


def allowed(chat_id: int) -> bool:
    allowed_ids = settings.telegram_allowed_chat_ids
    return not allowed_ids or chat_id in allowed_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Scores 2026 ativo. Use /status, /top_gols, /top_rating, /player nome ou /sync.')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        await update.message.reply_text('Chat não autorizado.')
        return
    db = SessionLocal()
    try:
        teams = db.query(Team).count()
        players = db.query(Player).count()
        await update.message.reply_text(f'Base atual: {teams} times e {players} jogadores.')
    finally:
        db.close()


async def top_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        await update.message.reply_text('Chat não autorizado.')
        return
    db = SessionLocal()
    try:
        rows = db.query(Player.name, PlayerStats.goals).join(PlayerStats).order_by(desc(PlayerStats.goals)).limit(10).all()
        text = '\\n'.join([f'{i+1}. {name}: {goals or 0}' for i, (name, goals) in enumerate(rows)]) or 'Sem estatísticas cadastradas.'
        await update.message.reply_text(text)
    finally:
        db.close()


async def top_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        await update.message.reply_text('Chat não autorizado.')
        return
    db = SessionLocal()
    try:
        rows = db.query(Player.name, PlayerStats.rating).join(PlayerStats).order_by(desc(PlayerStats.rating)).limit(10).all()
        text = '\\n'.join([f'{i+1}. {name}: {rating or 0}' for i, (name, rating) in enumerate(rows)]) or 'Sem estatísticas cadastradas.'
        await update.message.reply_text(text)
    finally:
        db.close()


async def player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        await update.message.reply_text('Chat não autorizado.')
        return
    term = ' '.join(context.args).strip()
    if not term:
        await update.message.reply_text('Use: /player nome')
        return
    db = SessionLocal()
    try:
        row = db.query(Player, Team.name).outerjoin(Team).filter(Player.name.ilike(f'%{term}%')).first()
        if not row:
            await update.message.reply_text('Jogador não encontrado.')
            return
        p, team = row
        await update.message.reply_text(f'{p.name}\\nTime: {team or "-"}\\nPosição: {p.position or "-"}\\nNacionalidade: {p.nationality or "-"}')
    finally:
        db.close()


async def sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        await update.message.reply_text('Chat não autorizado.')
        return
    await update.message.reply_text('Iniciando sincronização. Aguarde...')
    db = SessionLocal()
    try:
        message = sync_teams_and_players(db)
        await update.message.reply_text(message)
    finally:
        db.close()


def main():
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError('TELEGRAM_BOT_TOKEN não configurado.')
    Base.metadata.create_all(bind=engine)
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', start))
    app.add_handler(CommandHandler('status', status))
    app.add_handler(CommandHandler('top_gols', top_goals))
    app.add_handler(CommandHandler('top_rating', top_rating))
    app.add_handler(CommandHandler('player', player))
    app.add_handler(CommandHandler('sync', sync))
    app.run_polling()


if __name__ == '__main__':
    main()
