import { pgTable, serial, varchar,timestamp,integer } from "drizzle-orm/pg-core";

// type ChatMessage = {
//   userMessage: string;
//   agentResponse: string;
//   createdAt: string;
// };

// export const ChatList = pgTable("chatList", {
//   id: serial("id").primaryKey(),
//   userId: varchar("userId").notNull(),
//   userEmail: varchar("userEmail").notNull(),
//   userName: varchar("userName").notNull(),
//   chat: jsonb("chat").$type<ChatMessage[]>().notNull(),
//   createdAt: timestamp("createdAt").notNull(),
// });



export const Chats = pgTable("chats", {
  id: serial("id").primaryKey(),
  userId: varchar("userId").notNull().unique(),
  userEmail: varchar("userEmail").notNull(),
  userName: varchar("userName").notNull(),
  createdAt: timestamp("createdAt").defaultNow(),
});

export const Messages = pgTable("messages", {
  id: serial("id").primaryKey(),
  chatId: integer("chatId")
    .notNull()
    .references(() => Chats.id),
  role: varchar("role").notNull(), // "user" | "agent" 
  content: varchar("content").notNull(),
  createdAt: timestamp("createdAt").defaultNow(),
});