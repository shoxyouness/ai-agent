import React from "react";
import Spline from "@splinetool/react-spline/next";
import { PointerHighlight } from "@/components/ui/pointer-highlight";
import { FlipWords } from "@/components/ui/flip-words";
import { AnimatedShinyText } from "@/components/ui/animated-shiny-text";
import { cn } from "@/lib/utils";
import { AnimatedGradientText } from "@/components/ui/animated-gradient-text";
import { ChevronRight } from "lucide-react";
import { NoiseBackground } from "@/components/ui/noise-background";
import Link from "next/link";
import HomeNavbar from "./Nav";

const HomeHero = () => {
  const words = ["emails", "meetings", "searchs", "workflows"];

  return (
    <div className="fixed w-screen h-screen">
      <HomeNavbar />
      <div className="absolute top-1/2  -translate-y-1/2 left-9">
        <div className="flex flex-col items-start gap-8">
          {/* <div className=" flex  items-center justify-start">
            <div
              className={cn(
                "group rounded-full border border-black/5 bg-neutral-200 text-base text-white transition-all ease-in  dark:border-white/5 dark:bg-neutral-900 "
              )}
            >
              <AnimatedShinyText className="inline-flex items-center justify-center pl-6 pr-8 py-1 text-3xl transition ease-out  rounded-4xl ">
                <span>✨ Meet your personal AI agent</span>
              </AnimatedShinyText>
            </div>
          </div> */}
          <div className="group relative flex items-center justify-start rounded-full pl-6 pr-8 py-1.5 shadow-[inset_0_-8px_10px_#8fdfff1f] transition-shadow duration-500 ease-out hover:shadow-[inset_0_-5px_10px_#8fdfff3f]">
            <span
              className={cn(
                "animate-gradient absolute inset-0 block h-full w-full rounded-[inherit] bg-gradient-to-r from-[#ffaa40]/50 via-[#9c40ff]/50 to-[#ffaa40]/50 bg-[length:300%_100%] p-[1px]"
              )}
              style={{
                WebkitMask:
                  "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
                WebkitMaskComposite: "destination-out",
                mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
                maskComposite: "subtract",
                WebkitClipPath: "padding-box",
              }}
            />

            <AnimatedGradientText className="text-3xl font-medium">
              <span>✨ Meet your personal AI agent</span>
            </AnimatedGradientText>
          </div>

          <div className="max-w-4xl">
            <div className="text-6xl mx-auto font-bold text-neutral-600 uppercase">
              Your AI agent for
              <FlipWords words={words} /> <br />
              that actually gets things done
            </div>
          </div>

          <div className="max-w-3xl text-neutral-500">
            <span>
              Tell it what you need — it handles emails, scheduling, and contact management in seconds.
            </span>
          </div>

          <div className="flex items-center justify-start gap-6">
            <Link href="/docs">
              <div className=" flex  items-center justify-start">
                <div
                  className={cn(
                    " group rounded-full border border-black/5 bg-neutral-300 text-base text-white transition-all ease-in  dark:border-white/5 dark:bg-neutral-900 "
                  )}
                >
                  <AnimatedShinyText className="inline-flex items-center justify-center pl-6 pr-8 py-3 text-lg  transition ease-out  rounded-4xl ">
                    <span>Read the Docs</span>
                  </AnimatedShinyText>
                </div>
              </div>
            </Link>

            <Link href="/dashboard/chat" className="flex justify-center">
              <NoiseBackground
                containerClassName="w-fit p-2 rounded-full mx-auto"
                gradientColors={[
                  "rgb(255, 100, 150)",
                  "rgb(100, 150, 255)",
                  "rgb(255, 200, 100)",
                ]}
              >
                <button className="text-lg h-full w-full cursor-pointer rounded-full bg-linear-to-r from-neutral-100 via-neutral-100 to-white px-4 py-2 text-black shadow-[0px_2px_0px_0px_var(--color-neutral-50)_inset,0px_0.5px_1px_0px_var(--color-neutral-400)] transition-all duration-100 active:scale-98 dark:from-black dark:via-black dark:to-neutral-900 dark:text-white dark:shadow-[0px_1px_0px_0px_var(--color-neutral-950)_inset,0px_1px_0px_0px_var(--color-neutral-800)]">
                  Get Started
                </button>
              </NoiseBackground>
            </Link>
          </div>
        </div>
      </div>
      <div className="w-full h-[110vh]">
        <Spline scene="https://prod.spline.design/NNMwqWnw6qzKOHwR/scene.splinecode" />{" "}
      </div>
    </div>
  );
};

export default HomeHero;
