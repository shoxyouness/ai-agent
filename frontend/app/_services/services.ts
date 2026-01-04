import { eq, asc } from "drizzle-orm";
// import { Messages, Chats } from "@/configs/schema";
import { db } from "@/configs/db";
import { Chats, Messages } from "@/configs/schema";

export async function getChatByUserId(userId: string) {
  // 1. Get the chat
  const chat = await db.query.Chats.findFirst({
    where: eq(Chats.userId, userId),
  });

  if (!chat) {
    return null;
  }

  // 2. Get messages for this chat
  const messages = await db.query.Messages.findMany({
    where: eq(Messages.chatId, chat.id),
    orderBy: asc(Messages.createdAt),
  });

  // 3. Return combined result
  return {
    chat,
    messages,
  };
}

export async function sendMessage({
  userId,
  userEmail,
  userName,
  content,
}: {
  userId: string;
  userEmail: string;
  userName: string;
  content: { userRequest: string; agentResponse: string };
}) {
  if (!content.userRequest || !content.agentResponse) {
    return;
  }

  let chat = await db.query.Chats.findFirst({
    where: eq(Chats.userId, userId),
  });

  if (!chat) {
    [chat] = await db
      .insert(Chats)
      .values({ userId, userEmail, userName })
      .returning();
  }

  await db.insert(Messages).values({
    chatId: chat.id,
    role: "user",
    content: content.userRequest,
  });

  await db.insert(Messages).values({
    chatId: chat.id,
    role: "agent",
    content: content.agentResponse,
  });

  return { chatId: chat.id };
}
