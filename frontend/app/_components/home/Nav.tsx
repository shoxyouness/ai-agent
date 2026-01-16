"use client";

import Link from "next/link";
import {
  HoveredLink,
  Menu,
  MenuItem,
  ProductItem,
} from "@/components/ui/navbar-menu";
import { cn } from "@/lib/utils";
import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";
import Image from "next/image";
import { Brain } from "lucide-react";


const HomeNavbar = ({ className }: { className?: string }) => {
  const [active, setActive] = useState<string | null>(null);

  return (
    <div className="fixed top-2 px-8 inset-x-0  mx-auto z-50 flex items-center justify-between ">
      <Link href="/" className="flex items-center gap-3 group">
        <div className="w-10 h-10 rounded-xl bg-neutral-900 dark:bg-white flex items-center justify-center shadow-lg relative transition-transform group-hover:scale-105">
          <div className="absolute inset-0 bg-neutral-900 dark:bg-white rounded-xl blur-lg opacity-20 group-hover:opacity-40 transition-opacity"></div>
          <Brain size={24} className="text-white dark:text-neutral-900 relative z-10" />
        </div>
        <span className="text-xl font-bold tracking-tighter text-neutral-900 dark:text-white">
          AIPËR
        </span>
      </Link>

      <div className={cn("text-neutral-600", className)}>
        <Menu setActive={setActive}>
          <MenuItem setActive={setActive} active={active} item="Features">
            <div className="flex flex-col space-y-4 text-sm text-neutral-600">
              <HoveredLink href="/features/email">Email AI</HoveredLink>
              <HoveredLink href="/features/scheduler">
                Smart Scheduler
              </HoveredLink>
              <HoveredLink href="/features/research">Research Agent</HoveredLink>
              <HoveredLink href="/features/workflows">Workflow Automator</HoveredLink>
            </div>
          </MenuItem>
          <MenuItem setActive={setActive} active={active} item="Capabilities">
            <div className="  text-sm grid grid-cols-2 gap-10 p-4">
              <ProductItem
                title="Multi-Agent System"
                href="/capabilities/agents"
                src="https://assets.aceternity.com/demos/algochurn.webp"
                description="Specialized agents working together for you."
              />
              <ProductItem
                title="Voice Interaction"
                href="/capabilities/voice"
                src="https://assets.aceternity.com/demos/tailwindmasterkit.webp"
                description="Communicate with your agent via speech and phone."
              />
              <ProductItem
                title="Memory & Learning"
                href="/capabilities/memory"
                src="https://assets.aceternity.com/demos/Screenshot+2024-02-21+at+11.51.31%E2%80%AFPM.png"
                description="Your agent learns your preferences over time."
              />
              <ProductItem
                title="Secure Auth"
                href="/capabilities/security"
                src="https://assets.aceternity.com/demos/Screenshot+2024-02-21+at+11.47.07%E2%80%AFPM.png"
                description="Enterprise-grade security for your data."
              />
            </div>
          </MenuItem>
          <MenuItem setActive={setActive} active={active} item="Pricing">
            <div className="flex flex-col space-y-4 text-sm">
              <HoveredLink href="/pricing#free">Free</HoveredLink>
              <HoveredLink href="/pricing#pro">Pro</HoveredLink>
              <HoveredLink href="/pricing#business">Business</HoveredLink>
              <HoveredLink href="/pricing#enterprise">Enterprise</HoveredLink>
            </div>
          </MenuItem>
        </Menu>
      </div>
      <div className="flex items-center gap-2">
        <SignedOut>
          <SignInButton>
            <Button
              className="bg-neutral-600 hover:bg-neutral-700 ease-in-out duration-100 cursor-pointer"
              variant="default"
            >
              Sign In
            </Button>
          </SignInButton>
          <SignUpButton>
            <Button variant="outline" className="cursor-pointer">
              Sign Up
            </Button>
          </SignUpButton>
        </SignedOut>
        <SignedIn>
          <UserButton />
        </SignedIn>
      </div>

      {/* <header className="flex justify-end items-center p-4 gap-4 h-16">
            <SignedOut>
              <SignInButton />
              <SignUpButton>
                <button className="bg-[#6c47ff] text-ceramic-white rounded-full font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 cursor-pointer">
                  Sign Up
                </button>
              </SignUpButton>
            </SignedOut>
            <SignedIn>
              <UserButton />
            </SignedIn>
          </header> */}
    </div>
  );
};

export default HomeNavbar;
