"use client";
import React, { useState } from "react";
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { IconArrowLeft, IconUserBolt } from "@tabler/icons-react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { SignOutButton, UserButton, useUser } from "@clerk/nextjs";
import { LayoutDashboard, MessageCircle } from "lucide-react";

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const links = [
    {
      label: "Chat",
      href: "/dashboard/chat",
      icon: (
        <MessageCircle className="h-5 w-5 shrink-0 text-neutral-700 dark:text-neutral-200" />
      ),
    },
    // {
    //   label: "Profile",
    //   href: "/dashboard/profile",
    //   icon: (
    //     <IconUserBolt className="h-5 w-5 shrink-0 text-neutral-700 dark:text-neutral-200" />
    //   ),
    // },
    // {
    //   label: "Logout",
    //   href: "/",
    //   icon: (
    //     <IconArrowLeft className="h-5 w-5 shrink-0 text-neutral-700 dark:text-neutral-200" />
    //   ),
    // },
  ];
  const [open, setOpen] = useState(false);
  const { user, isLoaded } = useUser();

  return (
    <div
      className={cn(
        "flex w-full flex-1 flex-col overflow-hidden rounded-md border border-neutral-200 bg-gray-100 md:flex-row dark:border-neutral-700 dark:bg-neutral-800",
        "h-screen w-screen"
      )}
    >
      <Sidebar open={true} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-10">
          <div className="flex flex-1 flex-col overflow-x-hidden overflow-y-auto">
            {/* {open ? <Logo /> : <LogoIcon />} */}
            {<Logo />}
            <div className="mt-8 flex flex-col gap-2">
              {links.map((link, idx) =>
                links.length === idx + 1 ? (
                  <SignOutButton key={"signout-" + idx}>
                    <SidebarLink key={idx} link={link} />
                  </SignOutButton>
                ) : (
                  <SidebarLink key={idx} link={link} />
                )
              )}
            </div>
          </div>
          <div className="flex flex-col gap-4">
            <div
              className={`${"flex items-center justify-start gap-2 bg-gray-200 p-3 rounded-lg"}`}
            >
              <div className="pt-1">
                <UserButton />
              </div>
              <div>
                <h2 className="text-sm mb-1">
                  {user?.firstName} {user?.lastName}
                </h2>
                <h2 className="text-xs text-gray-500">
                  {user?.emailAddresses[0]?.emailAddress}
                </h2>
              </div>
            </div>
          </div>
        </SidebarBody>
      </Sidebar>
      <div className="flex flex-1 overflow-y-scroll">
        <div className="flex h-full w-full flex-1 flex-col rounded-tl-2xl border border-neutral-200 bg-white dark:border-neutral-700 dark:bg-neutral-900 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
};

export default DashboardLayout;

// 👇 helper components, not exported
function Logo() {
  return (
    <Link
      href="/"
      className="relative z-20 flex items-center space-x-2 py-1 text-sm font-normal text-black"
    >
      <div className="h-5 w-6 shrink-0 rounded-tl-lg rounded-tr-sm rounded-br-lg rounded-bl-sm bg-black dark:bg-white" />
      <motion.span
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="font-medium whitespace-pre text-black dark:text-white"
      >
        Launchly
      </motion.span>
    </Link>
  );
}

function LogoIcon() {
  return (
    <div className="relative z-20 flex items-center space-x-2 py-1 text-sm font-normal text-black">
      <div className="h-5 w-6 shrink-0 rounded-tl-lg rounded-tr-sm rounded-br-lg rounded-bl-sm bg-black dark:bg-white" />
    </div>
  );
}
