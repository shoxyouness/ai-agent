import { SignIn } from "@clerk/nextjs";

export default function Page() {
  return (
    <main className="flex h-screen w-full items-center justify-center bg-[#dfdede]">
      <SignIn 
        appearance={{
          variables: {
            colorPrimary: "#000000",
            colorText: "#1f2937",
            colorBackground: "oklch(97% 0 0)",
            borderRadius: "12px",
          },
          elements: {
            card: "shadow-xl border border-gray-200",
            headerTitle: "text-2xl font-bold",
            headerSubtitle: "text-sm text-gray-500",
            formButtonPrimary:
              "bg-black hover:bg-gray-800 text-white text-sm font-semibold",
            formFieldInput:
              "rounded-lg border border-gray-300 focus:border-black focus:ring-0",
            footerActionLink:
              "text-black font-medium hover:underline",
          },
        }}
      />
    </main>
  );
}
