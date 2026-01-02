import React from "react";
import { BackgroundLines } from "@/components/ui/background-lines";
import { ArrowUpFromDot } from "lucide-react";

export default function NewChat() {
  return (
    <BackgroundLines className="relative left-[1%] flex items-center justify-center ">
      <div className="w-full h-full flex flex-col items-center justify-center relative -top-[6%] left-[1%]">
      <h2 className="bg-clip-text text-transparent text-center bg-gradient-to-b from-neutral-900 to-neutral-700 dark:from-neutral-600 dark:to-white text-xl md:text-2xl lg:text-4xl font-sans py-2 md:py-10 relative z-20 font-bold tracking-tight">
        What’s on the agenda today?
      </h2>
      <div className="px-3 rounded-full border border-neutral-300 py-1 flex items-center justify-center gap-2">
        <input
          type="text"
          placeholder="Ask anything..."
          className="w-72 md:w-96 lg:w-[700px] rounded-full p-3 border-none bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 focus:outline-none "
        />
        <button className="w-10 h-10 rounded-full bg-neutral-900 flex items-center justify-center cursor-pointer hover:bg-neutral-700 transition-colors">
          <ArrowUpFromDot  size={20} className="text-white"/>
        </button>
      </div>
      </div>
    </BackgroundLines>
  );
}
