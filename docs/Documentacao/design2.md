# Códigos gerados (inspiração para cada sessão)


# Automações (Onde mostra dispostivos como cameras conectado)

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Aura Assist - Device Control Center</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&amp;family=JetBrains+Mono:wght@500;600&amp;family=Geist:wght@400;500;600&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
          darkMode: "class",
          theme: {
            extend: {
              "colors": {
                      "secondary": "#dfb7ff",
                      "on-error": "#690005",
                      "primary": "#baf2ff",
                      "tertiary-fixed": "#e2e2e2",
                      "on-tertiary-fixed": "#1b1b1b",
                      "on-tertiary-container": "#565656",
                      "outline-variant": "#3b494c",
                      "primary-fixed-dim": "#00daf8",
                      "inverse-on-surface": "#313030",
                      "error-container": "#93000a",
                      "surface-bright": "#393939",
                      "error": "#ffb4ab",
                      "surface-container-high": "#2a2a2a",
                      "inverse-primary": "#006877",
                      "surface": "#131313",
                      "inverse-surface": "#e5e2e1",
                      "primary-container": "#00e0ff",
                      "surface-container-lowest": "#0e0e0e",
                      "secondary-fixed-dim": "#dfb7ff",
                      "on-primary-fixed-variant": "#004e5a",
                      "surface-container-low": "#1c1b1b",
                      "on-error-container": "#ffdad6",
                      "surface-tint": "#00daf8",
                      "tertiary-container": "#cccccc",
                      "outline": "#859397",
                      "surface-dim": "#131313",
                      "on-secondary-fixed": "#2d004f",
                      "secondary-container": "#9d05ff",
                      "on-tertiary": "#303030",
                      "on-secondary-container": "#f7e6ff",
                      "on-primary-container": "#005f6d",
                      "on-surface": "#e5e2e1",
                      "tertiary": "#e8e8e8",
                      "secondary-fixed": "#f1daff",
                      "surface-container-highest": "#353534",
                      "on-surface-variant": "#bac9cd",
                      "surface-variant": "#353534",
                      "tertiary-fixed-dim": "#c6c6c6",
                      "on-tertiary-fixed-variant": "#474747",
                      "surface-container": "#201f1f",
                      "on-secondary": "#4b007e",
                      "on-primary": "#00363f",
                      "on-secondary-fixed-variant": "#6b00b0",
                      "on-background": "#e5e2e1",
                      "primary-fixed": "#a5eeff",
                      "background": "#131313",
                      "on-primary-fixed": "#001f25"
              },
              "borderRadius": {
                      "DEFAULT": "0.125rem",
                      "lg": "0.25rem",
                      "xl": "0.5rem",
                      "full": "0.75rem"
              },
              "spacing": {
                      "container-padding-desktop": "64px",
                      "card-padding-internal": "32px",
                      "gutter-desktop": "32px",
                      "gutter-mobile": "16px",
                      "container-padding-mobile": "24px",
                      "unit": "8px",
                      "stack-gap": "24px"
              },
              "fontFamily": {
                      "headline-md": ["Sora"],
                      "label-sm": ["JetBrains Mono"],
                      "body-lg": ["Geist"],
                      "headline-lg-mobile": ["Sora"],
                      "body-md": ["Geist"],
                      "label-md": ["JetBrains Mono"],
                      "body-sm": ["Geist"],
                      "headline-xl": ["Sora"],
                      "headline-lg": ["Sora"]
              },
              "fontSize": {
                      "headline-md": ["24px", {"lineHeight": "32px", "fontWeight": "600"}],
                      "label-sm": ["10px", {"lineHeight": "14px", "letterSpacing": "0.08em", "fontWeight": "600"}],
                      "body-lg": ["18px", {"lineHeight": "28px", "fontWeight": "400"}],
                      "headline-lg-mobile": ["28px", {"lineHeight": "36px", "fontWeight": "600"}],
                      "body-md": ["16px", {"lineHeight": "24px", "fontWeight": "400"}],
                      "label-md": ["12px", {"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "500"}],
                      "body-sm": ["14px", {"lineHeight": "20px", "fontWeight": "400"}],
                      "headline-xl": ["48px", {"lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700"}],
                      "headline-lg": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.01em", "fontWeight": "600"}]
              }
            },
          },
        }
      </script>
<style>
        body {
            background-color: #000000; /* Full Black override */
            color: #e5e2e1;
        }
        .void-border {
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .void-border-high {
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .ambient-shadow {
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8);
        }
        .neon-glow-primary {
            box-shadow: 0 0 15px rgba(0, 218, 248, 0.2);
        }
        .neon-glow-secondary {
            box-shadow: 0 0 15px rgba(223, 183, 255, 0.2);
        }
        .glass-surface {
            background: linear-gradient(180deg, rgba(32, 31, 31, 0.4) 0%, rgba(19, 19, 19, 0.8) 100%);
            backdrop-filter: blur(12px);
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 16px;
            width: 16px;
            border-radius: 50%;
            background: #00daf8;
            cursor: pointer;
            margin-top: -6px;
            box-shadow: 0 0 10px rgba(0, 218, 248, 0.5);
        }
        input[type=range]::-webkit-slider-runnable-track {
            width: 100%;
            height: 4px;
            cursor: pointer;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
        }
      </style>
</head>
<body class="antialiased min-h-screen flex flex-col md:flex-row">
<!-- Side Nav (Desktop) -->
<nav class="hidden md:flex fixed left-0 top-0 h-full flex-col py-8 z-40 bg-surface-container-lowest dark:bg-surface-container-lowest border-r border-white/10 shadow-2xl shadow-black w-64">
<div class="px-6 mb-12">
<h1 class="text-headline-lg font-headline-lg text-primary-fixed-dim">Aura Core</h1>
<p class="text-label-sm font-label-sm text-secondary-fixed-dim mt-2">Automation Active</p>
</div>
<button class="mx-6 mb-8 py-3 px-4 bg-gradient-to-r from-surface-container-highest to-surface-container border border-white/20 rounded text-body-md font-body-md text-white hover:neon-glow-primary transition-all flex items-center justify-center gap-2">
<span class="material-symbols-outlined text-[18px]">add</span> New Task
        </button>
<div class="flex-1 px-2 space-y-1">
<a class="text-primary-fixed-dim font-bold border-r-2 border-primary-fixed-dim pr-4 flex items-center gap-3 px-4 py-3 bg-white/5 rounded-lg" href="#">
<span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">dashboard</span>
<span class="text-label-md font-label-md">Dashboard</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all rounded-lg duration-200" href="#">
<span class="material-symbols-outlined">bolt</span>
<span class="text-label-md font-label-md">Automations</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all rounded-lg duration-200" href="#">
<span class="material-symbols-outlined">chat_bubble</span>
<span class="text-label-md font-label-md">Chat</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all rounded-lg duration-200" href="#">
<span class="material-symbols-outlined">calendar_today</span>
<span class="text-label-md font-label-md">Calendar</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all rounded-lg duration-200" href="#">
<span class="material-symbols-outlined">analytics</span>
<span class="text-label-md font-label-md">Analytics</span>
</a>
</div>
<div class="px-2 mt-auto space-y-1">
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all rounded-lg" href="#">
<span class="material-symbols-outlined">help</span>
<span class="text-label-md font-label-md">Help</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all rounded-lg" href="#">
<span class="material-symbols-outlined">logout</span>
<span class="text-label-md font-label-md">Sign Out</span>
</a>
</div>
</nav>
<!-- Top App Bar (Mobile Nav Alternative & Global Header) -->
<header class="md:hidden sticky top-0 z-50 flex items-center justify-between px-gutter-mobile w-full backdrop-blur-md h-16 border-b border-white/10 bg-background ambient-shadow">
<div class="text-headline-md font-headline-md font-bold text-primary-fixed-dim tracking-tight">Aura Assist</div>
<div class="flex items-center gap-4 text-on-surface-variant">
<button class="hover:text-primary-fixed-dim transition-colors"><span class="material-symbols-outlined">notifications</span></button>
<button class="hover:text-primary-fixed-dim transition-colors"><span class="material-symbols-outlined">settings</span></button>
</div>
</header>
<!-- Main Content Canvas -->
<main class="flex-1 md:ml-64 p-container-padding-mobile md:p-container-padding-desktop">
<header class="mb-12 flex justify-between items-end">
<div>
<h2 class="text-headline-xl font-headline-xl text-on-background">Device Control</h2>
<p class="text-body-lg font-body-lg text-on-surface-variant mt-2 max-w-2xl">Manage your connected environment.</p>
</div>
<!-- Hidden on mobile, handled in side nav -->
<div class="hidden md:flex items-center gap-4 text-on-surface-variant">
<button class="hover:text-primary-fixed-dim hover:bg-surface-variant/30 transition-colors p-2 rounded-full scale-95 active:scale-90 duration-150"><span class="material-symbols-outlined">notifications</span></button>
<img alt="User profile" class="w-10 h-10 rounded-full border border-white/20 object-cover" data-alt="A futuristic, high-contrast digital avatar portrait of a user profile in neon blue and deep black styling." src="https://lh3.googleusercontent.com/aida-public/AB6AXuBE2lgtUDGVUalJR9BQ1TlJV25-t17kGKT2I8oQrFzWtr3MU71euK5GRthN36YCMQTiIaty6Fx87Yx1ENvkj3keeKnl-DZdCgyajDjU8UgSPsv0OTnF1I5YVxqJewzSTB5xrwqKPrGE8_JE8o3-WcK_IHlIVNPVH6Ea72v6_iF9PTI_gHM8FN_xVb0hBANqbG1IQtUX3m2XnZB-B5Cxff_9Bmz9e2r3NwJTURDOFOcMuyaqYkc57QOegzvmStRLzI3WkBlaoGJGQ-E"/>
</div>
</header>
<!-- Bento Grid Layout -->
<div class="grid grid-cols-1 md:grid-cols-12 gap-stack-gap">
<!-- Primary Section: Lighting (Spans 8 columns) -->
<section class="md:col-span-8 glass-surface void-border rounded-xl p-card-padding-internal ambient-shadow flex flex-col relative overflow-hidden group">
<div class="absolute inset-0 bg-gradient-to-br from-primary-container/5 to-transparent pointer-events-none opacity-50 group-hover:opacity-100 transition-opacity duration-500"></div>
<div class="flex justify-between items-start mb-8 relative z-10">
<div class="flex items-center gap-3">
<span class="material-symbols-outlined text-primary-fixed-dim text-3xl" style="font-variation-settings: 'FILL' 1;">lightbulb</span>
<h3 class="text-headline-md font-headline-md">Studio Lighting</h3>
</div>
<label class="relative inline-flex items-center cursor-pointer">
<input checked="" class="sr-only peer" type="checkbox" value=""/>
<div class="w-11 h-6 bg-surface-container-high peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-fixed-dim neon-glow-primary"></div>
</label>
</div>
<div class="mt-auto relative z-10 space-y-6">
<div>
<div class="flex justify-between text-label-sm font-label-sm text-on-surface-variant mb-2">
<span>Brightness</span>
<span class="text-primary-fixed-dim">85%</span>
</div>
<input class="w-full appearance-none bg-transparent" max="100" min="0" type="range" value="85"/>
</div>
<div class="flex gap-4">
<button class="flex-1 py-2 rounded-lg border void-border-high bg-primary-fixed-dim/10 text-primary-fixed-dim text-label-md font-label-md hover:bg-primary-fixed-dim/20 transition-colors">Focus</button>
<button class="flex-1 py-2 rounded-lg border void-border bg-surface text-on-surface text-label-md font-label-md hover:border-white/30 transition-colors">Relax</button>
<button class="flex-1 py-2 rounded-lg border void-border bg-surface text-on-surface text-label-md font-label-md hover:border-white/30 transition-colors">Night</button>
</div>
</div>
</section>
<!-- Climate Control (Spans 4 columns) -->
<section class="md:col-span-4 glass-surface void-border rounded-xl p-card-padding-internal ambient-shadow flex flex-col justify-between items-center text-center relative overflow-hidden group">
<div class="absolute inset-0 bg-gradient-to-t from-secondary-container/10 to-transparent pointer-events-none"></div>
<div class="w-full flex justify-between items-center mb-4 relative z-10 text-on-surface-variant">
<span class="material-symbols-outlined">ac_unit</span>
<span class="text-label-sm font-label-sm uppercase tracking-widest text-secondary-fixed-dim">Climate</span>
<span class="material-symbols-outlined">more_vert</span>
</div>
<div class="relative z-10 my-8">
<div class="text-[64px] font-headline-xl font-bold text-white tracking-tighter leading-none mb-2" style="text-shadow: 0 0 20px rgba(223, 183, 255, 0.3);">72°</div>
<p class="text-label-md font-label-md text-on-surface-variant">Cooling to 68°</p>
</div>
<div class="flex gap-4 w-full relative z-10">
<button class="flex-1 h-12 rounded-full border void-border bg-surface hover:bg-white/5 flex items-center justify-center transition-colors">
<span class="material-symbols-outlined text-secondary-fixed-dim">remove</span>
</button>
<button class="flex-1 h-12 rounded-full border void-border bg-surface hover:bg-white/5 flex items-center justify-center transition-colors">
<span class="material-symbols-outlined text-secondary-fixed-dim">add</span>
</button>
</div>
</section>
<!-- Security Camera Feed (Spans 6 columns) -->
<section class="md:col-span-6 h-64 glass-surface void-border rounded-xl ambient-shadow relative overflow-hidden group">
<img alt="Camera Feed Front Door" class="absolute inset-0 w-full h-full object-cover opacity-60 mix-blend-luminosity group-hover:opacity-80 transition-opacity duration-700" data-alt="A high-contrast, security camera view of a modern, sleek entryway with dark walls and subtle neon floor lighting, captured in a cinematic, slightly distorted wide-angle perspective." src="https://lh3.googleusercontent.com/aida-public/AB6AXuBCjdXVz7kizqdyT81rG1fD7yWk10IfAIVn802mpGVeCJJdTToSl-CBrneHaDU1Hh4RICihXt94KgR1_maP9pVqMn8O2lC5ZA3F0lC383fQdc-79DBsfe1HbQIZ2Xph0dFRJvlRCIs6BHtFnW12M3UvdaDErxRZrQagVu7JLYbCuAGrHa3ZgHAxxqvkKSTbsSVrZs6bDkU8PyAQwpItD_S1gp8eusg_-VtQnjIoyl0uONNFTe5Zh9SaqjQb4-PgJdhp_oh3kvqPeaA"/>
<div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent"></div>
<div class="absolute top-4 left-4 right-4 flex justify-between items-center">
<div class="flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1 rounded-full void-border">
<div class="w-2 h-2 rounded-full bg-error animate-pulse"></div>
<span class="text-label-sm font-label-sm text-white">LIVE</span>
</div>
<span class="material-symbols-outlined text-white/70">fullscreen</span>
</div>
<div class="absolute bottom-4 left-4">
<h3 class="text-body-lg font-body-lg font-semibold text-white">Front Entry</h3>
<p class="text-label-sm font-label-sm text-on-surface-variant">Motion detected 2m ago</p>
</div>
</section>
<!-- Security Camera Feed 2 (Spans 6 columns) -->
<section class="md:col-span-6 h-64 glass-surface void-border rounded-xl ambient-shadow relative overflow-hidden group">
<img alt="Camera Feed Garage" class="absolute inset-0 w-full h-full object-cover opacity-40 mix-blend-luminosity group-hover:opacity-80 transition-opacity duration-700" data-alt="A stylized security camera view of a dark, minimalist garage space with a high-end sports car silhouette illuminated by a single overhead spotlight." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAzcnoLKdaAo67R_q9RoqS1m6CrKV3dtWq1nUCoZcpXnEo4l28EYex3pWqLHEWlbGSHNtqzoTaasXrL7dJ_T9yGWvDLmAYGmSrtGKl6y55u_Fto4RKMaAMHCqI3X-pUxHCsn-TSQpr1aYxftdzgJo2ilnqr4qTcduNqSd8ARdfZBkUSjfCu8sdCWPgHRJGrW4-EFmLMZlR-6zG9gaNiGm0i7lURjR2_FcuJJggCPDEdOITpouXjLnpXtQN48urzUrsTK0_R06v2IlQ"/>
<div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent"></div>
<div class="absolute top-4 left-4 right-4 flex justify-between items-center">
<div class="flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1 rounded-full void-border">
<div class="w-2 h-2 rounded-full bg-surface-variant"></div>
<span class="text-label-sm font-label-sm text-white/50">STANDBY</span>
</div>
</div>
<div class="absolute bottom-4 left-4">
<h3 class="text-body-lg font-body-lg font-semibold text-white">Garage</h3>
<p class="text-label-sm font-label-sm text-on-surface-variant">No recent activity</p>
</div>
</section>
<!-- Quick Actions / Door Locks (Spans 12 columns) -->
<section class="md:col-span-12 glass-surface void-border rounded-xl p-card-padding-internal ambient-shadow">
<h3 class="text-headline-md font-headline-md mb-6">Access Control</h3>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
<!-- Locked State -->
<button class="p-6 rounded-lg border border-primary-fixed-dim/30 bg-primary-fixed-dim/5 hover:bg-primary-fixed-dim/10 flex flex-col items-center justify-center gap-3 transition-all neon-glow-primary text-center">
<span class="material-symbols-outlined text-primary-fixed-dim text-3xl" style="font-variation-settings: 'FILL' 1;">lock</span>
<div>
<div class="text-body-sm font-body-sm text-white font-semibold">Front Door</div>
<div class="text-label-sm font-label-sm text-primary-fixed-dim">Locked</div>
</div>
</button>
<!-- Unlocked State -->
<button class="p-6 rounded-lg border void-border bg-surface-container hover:bg-surface-container-high flex flex-col items-center justify-center gap-3 transition-all text-center">
<span class="material-symbols-outlined text-on-surface-variant text-3xl">lock_open</span>
<div>
<div class="text-body-sm font-body-sm text-white font-semibold">Back Patio</div>
<div class="text-label-sm font-label-sm text-error">Unlocked</div>
</div>
</button>
<button class="p-6 rounded-lg border border-primary-fixed-dim/30 bg-primary-fixed-dim/5 hover:bg-primary-fixed-dim/10 flex flex-col items-center justify-center gap-3 transition-all neon-glow-primary text-center">
<span class="material-symbols-outlined text-primary-fixed-dim text-3xl" style="font-variation-settings: 'FILL' 1;">lock</span>
<div>
<div class="text-body-sm font-body-sm text-white font-semibold">Garage Side</div>
<div class="text-label-sm font-label-sm text-primary-fixed-dim">Locked</div>
</div>
</button>
<button class="p-6 rounded-lg border void-border bg-surface-container hover:bg-surface-container-high flex flex-col items-center justify-center gap-3 transition-all text-center">
<span class="material-symbols-outlined text-on-surface-variant text-3xl">meeting_room</span>
<div>
<div class="text-body-sm font-body-sm text-white font-semibold">Gate</div>
<div class="text-label-sm font-label-sm text-on-surface-variant">Closed</div>
</div>
</button>
</div>
</section>
</div>
</main>
</body></html>


--------------------------------------------------------------------------------------------------------------------------------------




# Calendar

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Aura Core | Calendar</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&amp;family=Geist:wght@300;400;500;600&amp;family=JetBrains+Mono:wght@500;600&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<!-- Tailwind Configuration -->
<script id="tailwind-config">
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            "colors": {
                "surface-container-low": "#1c1b1b",
                "on-surface": "#e5e2e1",
                "surface-container-highest": "#353534",
                "on-surface-variant": "#bac9cd",
                "primary-fixed-dim": "#00daf8",
                "primary-container": "#00e0ff",
                "secondary": "#dfb7ff",
                "primary": "#baf2ff",
                "secondary-container": "#9d05ff",
                "on-secondary-fixed": "#2d004f",
                "tertiary": "#e8e8e8",
                "on-tertiary": "#303030",
                "on-primary-fixed-variant": "#004e5a",
                "inverse-on-surface": "#313030",
                "on-primary": "#00363f",
                "surface-variant": "#353534",
                "surface-tint": "#00daf8",
                "on-primary-fixed": "#001f25",
                "tertiary-container": "#cccccc",
                "surface": "#131313",
                "background": "#131313",
                "outline-variant": "#3b494c",
                "on-primary-container": "#005f6d",
                "error": "#ffb4ab",
                "surface-bright": "#393939",
                "primary-fixed": "#a5eeff",
                "surface-container-high": "#2a2a2a",
                "on-background": "#e5e2e1",
                "surface-container-lowest": "#0e0e0e",
                "secondary-fixed-dim": "#dfb7ff",
                "surface-container": "#201f1f",
                "on-tertiary-container": "#565656",
                "on-tertiary-fixed-variant": "#474747",
                "on-error-container": "#ffdad6",
                "secondary-fixed": "#f1daff",
                "inverse-surface": "#e5e2e1",
                "on-tertiary-fixed": "#1b1b1b",
                "on-secondary": "#4b007e",
                "on-error": "#690005",
                "surface-dim": "#131313",
                "tertiary-fixed-dim": "#c6c6c6",
                "outline": "#859397",
                "on-secondary-container": "#f7e6ff",
                "tertiary-fixed": "#e2e2e2",
                "error-container": "#93000a",
                "on-secondary-fixed-variant": "#6b00b0",
                "inverse-primary": "#006877"
            },
            "borderRadius": {
                "DEFAULT": "0.125rem",
                "lg": "0.25rem",
                "xl": "0.5rem",
                "full": "0.75rem"
            },
            "spacing": {
                "stack-gap": "24px",
                "gutter-desktop": "32px",
                "container-padding-desktop": "64px",
                "unit": "8px",
                "gutter-mobile": "16px",
                "container-padding-mobile": "24px",
                "card-padding-internal": "32px"
            },
            "fontFamily": {
                "headline-lg-mobile": ["Sora"],
                "headline-md": ["Sora"],
                "body-md": ["Geist"],
                "headline-xl": ["Sora"],
                "body-sm": ["Geist"],
                "label-sm": ["JetBrains Mono"],
                "headline-lg": ["Sora"],
                "label-md": ["JetBrains Mono"],
                "body-lg": ["Geist"]
            },
            "fontSize": {
                "headline-lg-mobile": ["28px", {"lineHeight": "36px", "fontWeight": "600"}],
                "headline-md": ["24px", {"lineHeight": "32px", "fontWeight": "600"}],
                "body-md": ["16px", {"lineHeight": "24px", "fontWeight": "400"}],
                "headline-xl": ["48px", {"lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700"}],
                "body-sm": ["14px", {"lineHeight": "20px", "fontWeight": "400"}],
                "label-sm": ["10px", {"lineHeight": "14px", "letterSpacing": "0.08em", "fontWeight": "600"}],
                "headline-lg": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.01em", "fontWeight": "600"}],
                "label-md": ["12px", {"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "500"}],
                "body-lg": ["18px", {"lineHeight": "28px", "fontWeight": "400"}]
            }
          },
        },
      }
    </script>
<style>
        body {
            background-color: #000000;
            color: #e5e2e1;
            overflow-x: hidden;
        }
        .glass-card {
            background: rgba(19, 19, 19, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .neon-glow-blue {
            box-shadow: 0 0 15px rgba(0, 218, 248, 0.2);
        }
        .neon-glow-purple {
            box-shadow: 0 0 15px rgba(223, 183, 255, 0.2);
        }
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
        }
        .material-symbols-outlined {
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }
        .scrollbar-hide::-webkit-scrollbar {
            display: none;
        }
    </style>
</head>
<body class="font-body-md text-body-md">
<!-- Sidebar Navigation -->
<aside class="fixed left-0 top-0 h-full flex flex-col py-8 z-40 bg-surface-container-lowest border-r border-white/10 w-64 shadow-2xl shadow-black">
<div class="px-6 mb-12">
<h1 class="text-headline-lg font-headline-lg text-primary-fixed-dim">Aura Core</h1>
<div class="flex items-center gap-2 mt-2">
<span class="w-2 h-2 rounded-full bg-primary-fixed-dim animate-pulse"></span>
<span class="text-label-md font-label-md text-on-surface-variant">Automation Active</span>
</div>
</div>
<nav class="flex-1 space-y-2">
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined" data-icon="dashboard">dashboard</span>
<span class="font-label-md text-label-md">Dashboard</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined" data-icon="bolt">bolt</span>
<span class="font-label-md text-label-md">Automations</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined" data-icon="chat_bubble">chat_bubble</span>
<span class="font-label-md text-label-md">Chat</span>
</a>
<!-- Active State: Calendar -->
<a class="text-primary-fixed-dim font-bold border-r-2 border-primary-fixed-dim pr-4 flex items-center gap-3 px-6 py-3 bg-white/5 transition-all duration-200" href="#">
<span class="material-symbols-outlined" data-icon="calendar_today">calendar_today</span>
<span class="font-label-md text-label-md">Calendar</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined" data-icon="analytics">analytics</span>
<span class="font-label-md text-label-md">Analytics</span>
</a>
</nav>
<div class="px-6 mt-auto space-y-2">
<button class="w-full py-3 rounded-lg bg-primary-fixed-dim text-on-primary font-bold hover:scale-95 transition-transform duration-150 mb-6">
                New Task
            </button>
<a class="text-on-surface-variant flex items-center gap-3 py-2 hover:text-secondary-fixed-dim transition-colors" href="#">
<span class="material-symbols-outlined" data-icon="help">help</span>
<span class="font-label-md text-label-md">Help</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 py-2 hover:text-secondary-fixed-dim transition-colors" href="#">
<span class="material-symbols-outlined" data-icon="logout">logout</span>
<span class="font-label-md text-label-md">Sign Out</span>
</a>
</div>
</aside>
<!-- Main Content Area -->
<main class="ml-64 min-h-screen bg-black">
<!-- Top Navigation -->
<header class="sticky top-0 z-50 flex items-center justify-between px-gutter-desktop w-full h-16 border-b border-white/10 backdrop-blur-md bg-background/80">
<div class="flex items-center gap-4">
<h2 class="text-headline-md font-headline-md font-bold text-primary-fixed-dim tracking-tight">Aura Assist</h2>
</div>
<div class="flex items-center gap-6">
<div class="relative group">
<input class="bg-surface-container-low border border-white/10 rounded-full px-4 py-1.5 text-body-sm focus:outline-none focus:border-primary-fixed-dim transition-all w-64" placeholder="Search events..." type="text"/>
<span class="material-symbols-outlined absolute right-3 top-2 text-on-surface-variant text-[20px]" data-icon="search">search</span>
</div>
<div class="flex items-center gap-4">
<button class="text-on-surface-variant hover:text-primary-fixed-dim transition-colors">
<span class="material-symbols-outlined" data-icon="notifications">notifications</span>
</button>
<button class="text-on-surface-variant hover:text-primary-fixed-dim transition-colors">
<span class="material-symbols-outlined" data-icon="settings">settings</span>
</button>
<div class="w-8 h-8 rounded-full bg-surface-container-highest border border-white/20 overflow-hidden">
<img class="w-full h-full object-cover" data-alt="A professional headshot of a futuristic tech entrepreneur with subtle holographic lighting across their face, set against a deep black background with hints of electric blue neon. The portrait is high-contrast, moody, and conveys digital luxury and high performance." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDHdFgZy-W6T4wN4Eh0QNnPUO-rR0ZW3vP-6R0-gM6WP7ssPEzjyJtnUa8dqm4TSuIrvR2XNYdvdmsvE5yHFqxoKP9tjkcUaFUYddZb3cE2z66nopR1wmFQRCtp6L5R53HDENE__P3u8O-HfT1YEpww0qNERHWTvMg50cNufP3D8NCAkE5DGlJX1y0bG15KKS5RSqYCxLxcE4jkleb_m9UbFz3bks5FtyVi9Rqsepx22JpOV64qpaGUfJzPtMN-OWDp2FiQ69IIYOI"/>
</div>
</div>
</div>
</header>
<!-- Calendar Container -->
<div class="p-gutter-desktop max-w-[1600px] mx-auto grid grid-cols-12 gap-stack-gap">
<!-- Left Side: Monthly Grid -->
<section class="col-span-12 xl:col-span-8 flex flex-col gap-6">
<div class="flex items-center justify-between">
<div class="flex items-center gap-4">
<h3 class="font-headline-lg text-headline-lg text-white">October 2024</h3>
<div class="flex gap-1">
<button class="p-2 rounded-lg bg-surface-container-low border border-white/10 hover:border-primary-fixed-dim transition-colors">
<span class="material-symbols-outlined" data-icon="chevron_left">chevron_left</span>
</button>
<button class="p-2 rounded-lg bg-surface-container-low border border-white/10 hover:border-primary-fixed-dim transition-colors">
<span class="material-symbols-outlined" data-icon="chevron_right">chevron_right</span>
</button>
</div>
</div>
<div class="flex bg-surface-container-low rounded-lg p-1 border border-white/10">
<button class="px-4 py-1.5 rounded-md text-label-md font-label-md bg-white/10 text-white">Month</button>
<button class="px-4 py-1.5 rounded-md text-label-md font-label-md text-on-surface-variant hover:text-white transition-colors">Week</button>
<button class="px-4 py-1.5 rounded-md text-label-md font-label-md text-on-surface-variant hover:text-white transition-colors">Day</button>
</div>
</div>
<!-- Calendar View -->
<div class="glass-card rounded-xl overflow-hidden shadow-2xl">
<div class="calendar-grid border-b border-white/5 bg-surface-container-low">
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">SUN</div>
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">MON</div>
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">TUE</div>
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">WED</div>
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">THU</div>
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">FRI</div>
<div class="py-4 text-center text-label-md font-label-md text-on-surface-variant">SAT</div>
</div>
<div class="calendar-grid bg-transparent">
<!-- Dates (Simulated Grid) -->
<div class="h-32 border-r border-b border-white/5 p-3 opacity-20"><span class="text-label-md">29</span></div>
<div class="h-32 border-r border-b border-white/5 p-3 opacity-20"><span class="text-label-md">30</span></div>
<!-- Current Month Start -->
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">01</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">02</span>
<div class="mt-2 space-y-1">
<div class="px-2 py-1 rounded bg-secondary-container/20 border border-secondary-container/40 text-[10px] text-secondary font-medium flex items-center gap-1">
<span class="w-1 h-1 rounded-full bg-secondary"></span> System Refresh
                                </div>
</div>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">03</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">04</span>
</div>
<div class="h-32 border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">05</span>
</div>
<!-- Row 2 -->
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">06</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">07</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer bg-primary/5">
<span class="text-label-md text-primary-fixed-dim font-bold">08</span>
<div class="mt-2 space-y-1">
<div class="px-2 py-1 rounded bg-primary-container/20 border border-primary-container/40 text-[10px] text-primary-fixed-dim font-medium flex items-center gap-1">
<span class="w-1 h-1 rounded-full bg-primary-fixed-dim"></span> Logic Sync
                                </div>
<div class="px-2 py-1 rounded bg-white/5 border border-white/10 text-[10px] text-white/60 font-medium flex items-center gap-1">
<span class="w-1 h-1 rounded-full bg-white/40"></span> 14:00 Workshop
                                </div>
</div>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">09</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">10</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">11</span>
</div>
<div class="h-32 border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">12</span>
</div>
<!-- Row 3 -->
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">13</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">14</span>
<div class="mt-2 space-y-1">
<div class="px-2 py-1 rounded bg-secondary-container/20 border border-secondary-container/40 text-[10px] text-secondary font-medium flex items-center gap-1">
<span class="w-1 h-1 rounded-full bg-secondary"></span> Auto-Backup
                                </div>
</div>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">15</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">16</span>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">17</span>
<div class="mt-2 space-y-1">
<div class="px-2 py-1 rounded bg-primary-container/20 border border-primary-container/40 text-[10px] text-primary-fixed-dim font-medium flex items-center gap-1">
<span class="w-1 h-1 rounded-full bg-primary-fixed-dim"></span> UI Audit
                                </div>
</div>
</div>
<div class="h-32 border-r border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">18</span>
</div>
<div class="h-32 border-b border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">19</span>
</div>
<!-- Add more rows as needed to fill the month -->
<div class="h-32 border-r border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">20</span>
</div>
<div class="h-32 border-r border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">21</span>
</div>
<div class="h-32 border-r border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">22</span>
</div>
<div class="h-32 border-r border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">23</span>
</div>
<div class="h-32 border-r border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">24</span>
</div>
<div class="h-32 border-r border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">25</span>
</div>
<div class="h-32 border-white/5 p-3 hover:bg-white/5 transition-colors group cursor-pointer">
<span class="text-label-md text-on-surface-variant group-hover:text-white">26</span>
</div>
</div>
</div>
</section>
<!-- Right Side: Agenda -->
<section class="col-span-12 xl:col-span-4 flex flex-col gap-6">
<div class="flex items-center justify-between">
<h3 class="font-headline-md text-headline-md text-white">Upcoming Tasks</h3>
<button class="text-primary-fixed-dim hover:underline text-label-md font-label-md">View All</button>
</div>
<div class="space-y-4 overflow-y-auto scrollbar-hide max-h-[700px] pr-2">
<!-- Event 1: Automation -->
<div class="glass-card rounded-xl p-card-padding-internal hover:border-primary-fixed-dim/40 transition-all group">
<div class="flex items-start justify-between mb-4">
<div class="bg-primary-container/10 p-2 rounded-lg neon-glow-blue">
<span class="material-symbols-outlined text-primary-fixed-dim" data-icon="auto_awesome">auto_awesome</span>
</div>
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase tracking-widest">Automation</span>
</div>
<h4 class="font-headline-md text-headline-md text-white mb-2">Neural Network Sync</h4>
<p class="text-body-sm text-on-surface-variant mb-6">Autonomous optimization of core processing nodes. No manual oversight required.</p>
<div class="flex items-center justify-between">
<div class="flex items-center gap-2">
<span class="material-symbols-outlined text-[18px] text-primary-fixed-dim" data-icon="schedule">schedule</span>
<span class="text-label-md font-label-md text-white">09:00 AM</span>
</div>
<div class="flex -space-x-2">
<div class="w-6 h-6 rounded-full border border-background bg-surface-container-highest flex items-center justify-center text-[10px] font-bold">AI</div>
<div class="w-6 h-6 rounded-full border border-background bg-surface-container-highest flex items-center justify-center text-[10px] font-bold">SY</div>
</div>
</div>
</div>
<!-- Event 2: Personal -->
<div class="glass-card rounded-xl p-card-padding-internal hover:border-secondary/40 transition-all group relative overflow-hidden">
<div class="absolute top-0 right-0 p-4">
<span class="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
</div>
<div class="flex items-start justify-between mb-4">
<div class="bg-secondary-container/10 p-2 rounded-lg neon-glow-purple">
<span class="material-symbols-outlined text-secondary" data-icon="person">person</span>
</div>
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase tracking-widest">Personal</span>
</div>
<h4 class="font-headline-md text-headline-md text-white mb-2">Creative Direction Review</h4>
<p class="text-body-sm text-on-surface-variant mb-6">Evaluate new glassmorphism assets for the "Digital Luxury" expansion pack.</p>
<div class="flex items-center justify-between">
<div class="flex items-center gap-2">
<span class="material-symbols-outlined text-[18px] text-secondary" data-icon="schedule">schedule</span>
<span class="text-label-md font-label-md text-white">11:30 AM</span>
</div>
<div class="flex items-center gap-1 text-secondary text-label-sm">
<span class="material-symbols-outlined text-[14px]" data-icon="location_on">location_on</span>
                                Virtual Studio 04
                            </div>
</div>
</div>
<!-- Event 3: Reminder -->
<div class="glass-card rounded-xl p-card-padding-internal hover:border-white/20 transition-all group">
<div class="flex items-start justify-between mb-4">
<div class="bg-white/5 p-2 rounded-lg border border-white/10">
<span class="material-symbols-outlined text-white/60" data-icon="notifications_active">notifications_active</span>
</div>
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase tracking-widest">Reminder</span>
</div>
<h4 class="font-headline-md text-headline-md text-white/80 mb-2">Hardware Maintenance</h4>
<p class="text-body-sm text-on-surface-variant mb-6">Quarterly inspection of localized server clusters in North America.</p>
<div class="flex items-center justify-between">
<div class="flex items-center gap-2">
<span class="material-symbols-outlined text-[18px] text-on-surface-variant" data-icon="schedule">schedule</span>
<span class="text-label-md font-label-md text-white/80">03:00 PM</span>
</div>
<button class="text-primary-fixed-dim hover:text-white transition-colors">
<span class="material-symbols-outlined" data-icon="arrow_forward">arrow_forward</span>
</button>
</div>
</div>
<!-- Add Event Placeholder -->
<button class="w-full h-24 border-2 border-dashed border-white/10 rounded-xl flex items-center justify-center gap-3 hover:border-primary-fixed-dim/30 transition-all text-on-surface-variant hover:text-primary-fixed-dim group">
<span class="material-symbols-outlined group-hover:rotate-90 transition-transform duration-300" data-icon="add">add</span>
<span class="font-label-md text-label-md">Schedule New Event</span>
</button>
</div>
<!-- Small Stats Card -->
<div class="mt-4 p-6 rounded-xl bg-gradient-to-br from-surface-container-high to-black border border-white/10 shadow-lg">
<div class="flex items-center justify-between mb-2">
<span class="text-label-md text-on-surface-variant">Active Reminders</span>
<span class="text-headline-md font-bold text-primary-fixed-dim">12</span>
</div>
<div class="w-full h-1 bg-white/10 rounded-full overflow-hidden">
<div class="h-full bg-primary-fixed-dim w-[65%]"></div>
</div>
<p class="text-[10px] text-on-surface-variant mt-2">65% of your daily goals achieved</p>
</div>
</section>
</div>
</main>
<!-- Floating Action Button -->
<button class="fixed bottom-8 right-8 w-14 h-14 rounded-full bg-primary-fixed-dim text-on-primary flex items-center justify-center shadow-[0_0_20px_rgba(0,218,248,0.4)] hover:scale-110 active:scale-95 transition-all duration-200 z-50">
<span class="material-symbols-outlined" data-icon="edit">edit</span>
</button>
<script>
        // Micro-interactions for calendar cells
        document.querySelectorAll('.calendar-grid > div').forEach(cell => {
            cell.addEventListener('mousedown', () => {
                cell.style.transform = 'scale(0.98)';
            });
            cell.addEventListener('mouseup', () => {
                cell.style.transform = 'scale(1)';
            });
            cell.addEventListener('mouseleave', () => {
                cell.style.transform = 'scale(1)';
            });
        });

        // Hover effects for agenda cards
        document.querySelectorAll('.glass-card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-4px)';
            });
            card.addEventListener('mouseleave', () => {
                card.style.transform = 'translateY(0)';
            });
        });
    </script>
</body></html>




--------------------------------------------------------------------------------------------------------------------------------------







# Analytics

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Aura Core | Analytics</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&amp;family=Geist:wght@400;500&amp;family=JetBrains+Mono:wght@500;600&amp;family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@100..900&amp;family=JetBrains+Mono:wght@100..900&amp;family=Sora:wght@100..900&amp;display=swap" rel="stylesheet"/>
<style>
        .material-symbols-outlined {
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }
        body {
            background-color: #131313;
            color: #e5e2e1;
            overflow-x: hidden;
        }
        .glass-card {
            background: rgba(20, 20, 20, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .neon-glow-primary {
            box-shadow: 0 0 15px rgba(0, 218, 248, 0.15);
        }
        .chart-gradient-line {
            filter: drop-shadow(0 0 8px rgba(0, 218, 248, 0.6));
        }
        @keyframes pulse-subtle {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .animate-pulse-subtle {
            animation: pulse-subtle 3s ease-in-out infinite;
        }
    </style>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "surface-container-low": "#1c1b1b",
                        "on-surface": "#e5e2e1",
                        "surface-container-highest": "#353534",
                        "on-surface-variant": "#bac9cd",
                        "primary-fixed-dim": "#00daf8",
                        "primary-container": "#00e0ff",
                        "secondary": "#dfb7ff",
                        "primary": "#baf2ff",
                        "secondary-container": "#9d05ff",
                        "on-secondary-fixed": "#2d004f",
                        "tertiary": "#e8e8e8",
                        "on-tertiary": "#303030",
                        "on-primary-fixed-variant": "#004e5a",
                        "inverse-on-surface": "#313030",
                        "on-primary": "#00363f",
                        "surface-variant": "#353534",
                        "surface-tint": "#00daf8",
                        "on-primary-fixed": "#001f25",
                        "tertiary-container": "#cccccc",
                        "surface": "#131313",
                        "background": "#131313",
                        "outline-variant": "#3b494c",
                        "on-primary-container": "#005f6d",
                        "error": "#ffb4ab",
                        "surface-bright": "#393939",
                        "primary-fixed": "#a5eeff",
                        "surface-container-high": "#2a2a2a",
                        "on-background": "#e5e2e1",
                        "surface-container-lowest": "#0e0e0e",
                        "secondary-fixed-dim": "#dfb7ff",
                        "surface-container": "#201f1f",
                        "on-tertiary-container": "#565656",
                        "on-tertiary-fixed-variant": "#474747",
                        "on-error-container": "#ffdad6",
                        "secondary-fixed": "#f1daff",
                        "inverse-surface": "#e5e2e1",
                        "on-tertiary-fixed": "#1b1b1b",
                        "on-secondary": "#4b007e",
                        "on-error": "#690005",
                        "surface-dim": "#131313",
                        "tertiary-fixed-dim": "#c6c6c6",
                        "outline": "#859397",
                        "on-secondary-container": "#f7e6ff",
                        "tertiary-fixed": "#e2e2e2",
                        "error-container": "#93000a",
                        "on-secondary-fixed-variant": "#6b00b0",
                        "inverse-primary": "#006877"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    "spacing": {
                        "stack-gap": "24px",
                        "gutter-desktop": "32px",
                        "container-padding-desktop": "64px",
                        "unit": "8px",
                        "gutter-mobile": "16px",
                        "container-padding-mobile": "24px",
                        "card-padding-internal": "32px"
                    },
                    "fontFamily": {
                        "headline-lg-mobile": ["Sora"],
                        "headline-md": ["Sora"],
                        "body-md": ["Geist"],
                        "headline-xl": ["Sora"],
                        "body-sm": ["Geist"],
                        "label-sm": ["JetBrains Mono"],
                        "headline-lg": ["Sora"],
                        "label-md": ["JetBrains Mono"],
                        "body-lg": ["Geist"]
                    },
                    "fontSize": {
                        "headline-lg-mobile": ["28px", {"lineHeight": "36px", "fontWeight": "600"}],
                        "headline-md": ["24px", {"lineHeight": "32px", "fontWeight": "600"}],
                        "body-md": ["16px", {"lineHeight": "24px", "fontWeight": "400"}],
                        "headline-xl": ["48px", {"lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700"}],
                        "body-sm": ["14px", {"lineHeight": "20px", "fontWeight": "400"}],
                        "label-sm": ["10px", {"lineHeight": "14px", "letterSpacing": "0.08em", "fontWeight": "600"}],
                        "headline-lg": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.01em", "fontWeight": "600"}],
                        "label-md": ["12px", {"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "500"}],
                        "body-lg": ["18px", {"lineHeight": "28px", "fontWeight": "400"}]
                    }
                },
            },
        }
    </script>
</head>
<body class="bg-background text-on-surface font-body-md">
<!-- Sidebar Navigation -->
<aside class="fixed left-0 top-0 h-full flex flex-col py-8 z-40 h-screen w-64 border-r border-white/10 bg-surface-container-lowest shadow-2xl shadow-black">
<div class="px-6 mb-12">
<h1 class="text-headline-lg font-headline-lg text-primary-fixed-dim">Aura Core</h1>
<div class="flex items-center gap-2 mt-2 opacity-80">
<div class="w-2 h-2 rounded-full bg-primary-fixed-dim animate-pulse"></div>
<span class="text-label-md font-label-md uppercase tracking-widest text-on-surface-variant">Automation Active</span>
</div>
</div>
<nav class="flex-1 flex flex-col gap-2">
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined" data-icon="dashboard">dashboard</span>
<span class="text-label-md font-label-md">Dashboard</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined" data-icon="bolt">bolt</span>
<span class="text-label-md font-label-md">Automations</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined" data-icon="chat_bubble">chat_bubble</span>
<span class="text-label-md font-label-md">Chat</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined" data-icon="calendar_today">calendar_today</span>
<span class="text-label-md font-label-md">Calendar</span>
</a>
<a class="text-primary-fixed-dim font-bold border-r-2 border-primary-fixed-dim pr-4 flex items-center gap-3 px-6 py-3 bg-white/5" href="#">
<span class="material-symbols-outlined" data-icon="analytics">analytics</span>
<span class="text-label-md font-label-md">Analytics</span>
</a>
</nav>
<div class="px-6 py-8 flex flex-col gap-4 border-t border-white/5 mt-auto">
<a class="text-on-surface-variant flex items-center gap-3 hover:text-primary-fixed-dim transition-colors" href="#">
<span class="material-symbols-outlined" data-icon="help">help</span>
<span class="text-label-md font-label-md">Help</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 hover:text-error transition-colors" href="#">
<span class="material-symbols-outlined" data-icon="logout">logout</span>
<span class="text-label-md font-label-md">Sign Out</span>
</a>
</div>
</aside>
<!-- Main Content Area -->
<main class="ml-64 min-h-screen">
<!-- Top Navigation Bar -->
<header class="sticky top-0 z-50 flex items-center justify-between px-gutter-desktop h-16 w-full backdrop-blur-md bg-background/80 border-b border-white/10">
<div class="flex items-center gap-4">
<span class="text-headline-md font-headline-md font-bold text-primary-fixed-dim tracking-tight">System Performance</span>
</div>
<div class="flex items-center gap-6">
<div class="relative">
<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none" data-icon="search">search</span>
<input class="bg-surface-container-low border-none rounded-full pl-10 pr-4 py-1.5 text-body-sm w-64 focus:ring-1 focus:ring-primary-fixed-dim transition-all" placeholder="Search analytics..." type="text"/>
</div>
<button class="text-on-surface-variant hover:text-primary-fixed-dim transition-transform active:scale-90 duration-150">
<span class="material-symbols-outlined" data-icon="notifications">notifications</span>
</button>
<button class="text-on-surface-variant hover:text-primary-fixed-dim transition-transform active:scale-90 duration-150">
<span class="material-symbols-outlined" data-icon="settings">settings</span>
</button>
<div class="w-8 h-8 rounded-full overflow-hidden border border-primary-fixed-dim/30">
<img class="w-full h-full object-cover" data-alt="A cinematic, high-fashion profile portrait of a futuristic tech executive. The person has sharp features, wearing a sleek black high-collar garment with subtle integrated fiber-optic threads. The lighting is dramatic high-contrast noir style with a soft electric blue rim light against a pure black background. 8k resolution, professional studio lighting." src="https://lh3.googleusercontent.com/aida-public/AB6AXuADJ8OsJI_MxlyqLZmqg3j2QWDfGDqoP6G0weu71H5AVNkTzOhyxCREuUSiknJgCR9prhqHoeIu54cvrPm1DyxlVdpaICkmL4JJxBzVgjtRQnja-F3Mquupey_PGQDzodEuC_ev0y9vPyLja5mEJs9yqNxyBVuvVDaTivkDkSRA7dN7CaWUi2xO4D1PyPPvr3DXGjUdpEKln8NpyMu8ApKEo74dE9JV8ulcWoUQXXfJBwBiSgLZW4uA9_9L69tX5dV42sRVIxk9YIA"/>
</div>
</div>
</header>
<!-- Analytics Grid Container -->
<div class="p-gutter-desktop max-w-[1600px] mx-auto space-y-stack-gap">
<!-- Summary Header Row -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-stack-gap">
<!-- Efficiency Score Card -->
<div class="glass-card p-card-padding-internal flex flex-col justify-between relative overflow-hidden group">
<div class="absolute top-0 right-0 w-32 h-32 bg-primary-fixed-dim/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:bg-primary-fixed-dim/10 transition-colors"></div>
<div>
<span class="text-label-md font-label-md text-on-surface-variant uppercase tracking-widest block mb-1">Efficiency Score</span>
<h2 class="text-headline-xl font-headline-xl text-primary-fixed-dim">94.2</h2>
</div>
<div class="mt-8">
<div class="flex justify-between items-end mb-2">
<span class="text-body-sm font-body-sm text-on-surface-variant">Optimal Range</span>
<span class="text-body-sm font-body-sm text-primary-fixed-dim">+2.4% vs last week</span>
</div>
<div class="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
<div class="h-full bg-primary-fixed-dim neon-glow-primary" style="width: 94.2%"></div>
</div>
</div>
</div>
<!-- Weekly Automation Success -->
<div class="glass-card p-card-padding-internal group transition-all">
<div class="flex justify-between items-start mb-6">
<span class="text-label-md font-label-md text-on-surface-variant uppercase tracking-widest">Automation Success</span>
<span class="material-symbols-outlined text-secondary-fixed-dim" data-icon="auto_awesome">auto_awesome</span>
</div>
<div class="flex items-end gap-2">
<div class="flex-1 flex items-end gap-1.5 h-24">
<div class="bg-surface-container-highest w-full rounded-t-sm group-hover:bg-primary-fixed-dim/40 transition-all duration-300 h-[60%]"></div>
<div class="bg-surface-container-highest w-full rounded-t-sm group-hover:bg-primary-fixed-dim/40 transition-all duration-300 h-[75%]"></div>
<div class="bg-surface-container-highest w-full rounded-t-sm group-hover:bg-primary-fixed-dim/40 transition-all duration-300 h-[70%]"></div>
<div class="bg-surface-container-highest w-full rounded-t-sm group-hover:bg-primary-fixed-dim/40 transition-all duration-300 h-[90%]"></div>
<div class="bg-primary-fixed-dim w-full rounded-t-sm neon-glow-primary h-[98%]"></div>
</div>
<div class="pl-4">
<span class="text-headline-md font-headline-md text-on-surface block leading-none">98%</span>
<span class="text-label-sm font-label-sm text-on-surface-variant">CURRENT RATE</span>
</div>
</div>
</div>
<!-- Active Systems Overview -->
<div class="glass-card p-card-padding-internal flex items-center justify-between">
<div>
<span class="text-label-md font-label-md text-on-surface-variant uppercase tracking-widest block mb-4">Network Status</span>
<div class="space-y-3">
<div class="flex items-center gap-3">
<div class="w-1.5 h-1.5 rounded-full bg-primary-fixed-dim"></div>
<span class="text-body-sm text-on-surface">Core Processing: Nominal</span>
</div>
<div class="flex items-center gap-3">
<div class="w-1.5 h-1.5 rounded-full bg-primary-fixed-dim"></div>
<span class="text-body-sm text-on-surface">Device Sync: Active</span>
</div>
<div class="flex items-center gap-3">
<div class="w-1.5 h-1.5 rounded-full bg-secondary-fixed-dim"></div>
<span class="text-body-sm text-on-surface">External Relays: Encrypted</span>
</div>
</div>
</div>
<div class="h-24 w-24 relative">

</div>
</div>
</div>
<!-- Main Charts Row: Energy & Distribution -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-stack-gap">
<!-- Energy Consumption Trend (Line Chart) -->
<div class="lg:col-span-2 glass-card p-card-padding-internal h-[480px] flex flex-col">
<div class="flex justify-between items-center mb-8">
<div>
<h3 class="text-headline-md font-headline-md text-on-surface">Energy Consumption</h3>
<span class="text-label-md font-label-md text-on-surface-variant">KW/H OVER THE LAST 24 HOURS</span>
</div>
<div class="flex gap-2">
<button class="px-4 py-1.5 bg-surface-container-highest text-label-sm rounded-full text-on-surface border border-white/5 hover:border-primary-fixed-dim transition-colors">LIVE</button>
<button class="px-4 py-1.5 bg-surface-container-lowest text-label-sm rounded-full text-on-surface-variant border border-white/5 hover:bg-white/5 transition-colors">HISTORY</button>
</div>
</div>
<div class="flex-1 relative mt-4 border-l border-b border-white/10">
<!-- Chart Mockup with SVG -->
<svg class="w-full h-full overflow-visible" preserveaspectratio="none" viewbox="0 0 1000 300">
<defs>
<lineargradient id="neonGradient" x1="0%" x2="0%" y1="0%" y2="100%">
<stop offset="0%" stop-color="rgba(0, 218, 248, 0.3)"></stop>
<stop offset="100%" stop-color="rgba(0, 218, 248, 0)"></stop>
</lineargradient>
</defs>
<!-- Grid lines -->
<line stroke="rgba(255,255,255,0.05)" x1="0" x2="1000" y1="75" y2="75"></line>
<line stroke="rgba(255,255,255,0.05)" x1="0" x2="1000" y1="150" y2="150"></line>
<line stroke="rgba(255,255,255,0.05)" x1="0" x2="1000" y1="225" y2="225"></line>
<!-- Area fill -->
<path d="M0,250 Q100,200 200,220 T400,100 T600,180 T800,120 T1000,80 V300 H0 Z" fill="url(#neonGradient)"></path>
<!-- Main Line -->
<path class="chart-gradient-line" d="M0,250 Q100,200 200,220 T400,100 T600,180 T800,120 T1000,80" fill="none" stroke="#00daf8" stroke-width="3"></path>
<!-- Hover point indicator -->
<circle class="animate-pulse" cx="800" cy="120" fill="#00daf8" r="6"></circle>
<circle class="animate-ping" cx="800" cy="120" fill="none" r="12" stroke="#00daf8" stroke-width="1" style="animation-duration: 2s;"></circle>
</svg>
<!-- Tooltip Mockup -->
<div class="absolute top-[100px] left-[780px] -translate-x-1/2 -translate-y-full glass-card px-4 py-2 pointer-events-none border-primary-fixed-dim/30">
<span class="text-label-sm text-primary-fixed-dim block">19:42 PM</span>
<span class="text-headline-md font-headline-md">1.24 kW/h</span>
</div>
</div>
<div class="flex justify-between mt-4 text-label-sm text-on-surface-variant font-label-sm px-2">
<span>00:00</span>
<span>06:00</span>
<span>12:00</span>
<span>18:00</span>
<span>NOW</span>
</div>
</div>
<!-- Device Usage Distribution (Donut Chart) -->
<div class="glass-card p-card-padding-internal h-[480px] flex flex-col">
<h3 class="text-headline-md font-headline-md text-on-surface mb-2">Device Distribution</h3>
<span class="text-label-md font-label-md text-on-surface-variant mb-12 uppercase tracking-widest">ACTIVE RESOURCE ALLOCATION</span>
<div class="flex-1 flex flex-col items-center justify-center relative">
<!-- Custom CSS/SVG Donut -->
<div class="relative w-48 h-48">
<svg class="w-full h-full -rotate-90" viewbox="0 0 100 100">
<circle cx="50" cy="50" fill="none" r="40" stroke="rgba(255,255,255,0.05)" stroke-width="8"></circle>
<circle class="neon-glow-primary" cx="50" cy="50" fill="none" r="40" stroke="#00daf8" stroke-dasharray="125 251.2" stroke-linecap="round" stroke-width="8"></circle>
<circle cx="50" cy="50" fill="none" r="40" stroke="#dfb7ff" stroke-dasharray="75 251.2" stroke-dashoffset="-130" stroke-linecap="round" stroke-width="8"></circle>
<circle cx="50" cy="50" fill="none" r="40" stroke="#e8e8e8" stroke-dasharray="51.2 251.2" stroke-dashoffset="-210" stroke-linecap="round" stroke-width="8"></circle>
</svg>
<div class="absolute inset-0 flex flex-col items-center justify-center">
<span class="text-headline-md font-headline-md text-on-surface">24</span>
<span class="text-label-sm text-on-surface-variant">TOTAL UNITS</span>
</div>
</div>
<div class="mt-12 w-full space-y-4">
<div class="flex justify-between items-center px-4 py-3 bg-white/5 rounded-lg border border-white/5">
<div class="flex items-center gap-3">
<div class="w-3 h-3 rounded-full bg-primary-fixed-dim"></div>
<span class="text-body-sm text-on-surface">HVAC Systems</span>
</div>
<span class="text-label-md font-label-md text-primary-fixed-dim">42%</span>
</div>
<div class="flex justify-between items-center px-4 py-3 bg-white/5 rounded-lg border border-white/5">
<div class="flex items-center gap-3">
<div class="w-3 h-3 rounded-full bg-secondary-fixed-dim"></div>
<span class="text-body-sm text-on-surface">Illumination</span>
</div>
<span class="text-label-md font-label-md text-secondary-fixed-dim">34%</span>
</div>
<div class="flex justify-between items-center px-4 py-3 bg-white/5 rounded-lg border border-white/5">
<div class="flex items-center gap-3">
<div class="w-3 h-3 rounded-full bg-tertiary"></div>
<span class="text-body-sm text-on-surface">Security Nodes</span>
</div>
<span class="text-label-md font-label-md text-on-surface-variant">24%</span>
</div>
</div>
</div>
</div>
</div>
<!-- Lower Bento Section -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-stack-gap">
<!-- Data Point 1 -->
<div class="glass-card p-card-padding-internal flex flex-col gap-2">
<span class="material-symbols-outlined text-primary-fixed-dim mb-2" data-icon="thermostat">thermostat</span>
<span class="text-label-md font-label-md text-on-surface-variant">AVG TEMPERATURE</span>
<div class="flex items-end gap-2">
<span class="text-headline-md font-headline-md">21.5°C</span>
<span class="text-body-sm text-primary-fixed-dim mb-1">STABLE</span>
</div>
</div>
<!-- Data Point 2 -->
<div class="glass-card p-card-padding-internal flex flex-col gap-2">
<span class="material-symbols-outlined text-secondary-fixed-dim mb-2" data-icon="cloud_done">cloud_done</span>
<span class="text-label-md font-label-md text-on-surface-variant">CLOUD UPTIME</span>
<div class="flex items-end gap-2">
<span class="text-headline-md font-headline-md">99.99%</span>
<span class="text-body-sm text-secondary-fixed-dim mb-1">ULTRA</span>
</div>
</div>
<!-- Data Point 3 -->
<div class="glass-card p-card-padding-internal flex flex-col gap-2">
<span class="material-symbols-outlined text-tertiary mb-2" data-icon="memory">memory</span>
<span class="text-label-md font-label-md text-on-surface-variant">CPU LOAD</span>
<div class="flex items-end gap-2">
<span class="text-headline-md font-headline-md">14.2%</span>
<span class="text-body-sm text-on-surface-variant mb-1">IDLE</span>
</div>
</div>
<!-- Data Point 4 -->
<div class="glass-card p-card-padding-internal flex flex-col gap-2">
<span class="material-symbols-outlined text-error mb-2" data-icon="security">security</span>
<span class="text-label-md font-label-md text-on-surface-variant">THREATS BLOCKED</span>
<div class="flex items-end gap-2">
<span class="text-headline-md font-headline-md">0</span>
<span class="text-body-sm text-error mb-1">SECURE</span>
</div>
</div>
</div>
<!-- Aesthetic Background Element -->
<div class="fixed bottom-0 right-0 w-1/3 h-1/2 -z-10 pointer-events-none opacity-20">

</div>
</div>
</main>
<script>
        // Simple micro-interaction for the donut chart or active states
        document.querySelectorAll('.glass-card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.style.borderColor = 'rgba(0, 218, 248, 0.3)';
                card.style.transform = 'translateY(-2px)';
            });
            card.addEventListener('mouseleave', () => {
                card.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                card.style.transform = 'translateY(0)';
            });
        });

        // Simulating live data update for the line chart
        setInterval(() => {
            const point = document.querySelector('.animate-pulse');
            if (point) {
                const randomOffset = (Math.random() - 0.5) * 5;
                const currentTop = parseInt(point.parentElement.parentElement.querySelector('.absolute').style.top) || 100;
                // Just visual jitter for effect
            }
        }, 3000);
    </script>
</body></html>





--------------------------------------------------------------------------------------------------------------------------------------









# Continuação Analytics

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Aura Core | Security Log</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&amp;family=Geist:wght@400;500;700&amp;family=JetBrains+Mono:wght@500;600&amp;family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@100..900&amp;family=JetBrains+Mono:wght@100..900&amp;family=Sora:wght@100..900&amp;display=swap" rel="stylesheet"/>
<style>
        .material-symbols-outlined {
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }
        .glass-panel {
            background: rgba(14, 14, 14, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .neon-glow-primary {
            box-shadow: 0 0 15px rgba(0, 218, 248, 0.15);
        }
        .neon-glow-error {
            box-shadow: 0 0 20px rgba(147, 0, 10, 0.4);
        }
        .obsidian-gradient {
            background: linear-gradient(135deg, #00daf8 0%, #9d05ff 100%);
        }
        body {
            background-color: #0e0e0e;
            color: #e5e2e1;
            overflow-x: hidden;
        }
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0e0e0e;
        }
        ::-webkit-scrollbar-thumb {
            background: #353534;
            border-radius: 10px;
        }
    </style>
<!-- Tailwind Theme Configuration -->
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "surface-container-low": "#1c1b1b",
                        "on-surface": "#e5e2e1",
                        "surface-container-highest": "#353534",
                        "on-surface-variant": "#bac9cd",
                        "primary-fixed-dim": "#00daf8",
                        "primary-container": "#00e0ff",
                        "secondary": "#dfb7ff",
                        "primary": "#baf2ff",
                        "secondary-container": "#9d05ff",
                        "on-secondary-fixed": "#2d004f",
                        "tertiary": "#e8e8e8",
                        "on-tertiary": "#303030",
                        "on-primary-fixed-variant": "#004e5a",
                        "inverse-on-surface": "#313030",
                        "on-primary": "#00363f",
                        "surface-variant": "#353534",
                        "surface-tint": "#00daf8",
                        "on-primary-fixed": "#001f25",
                        "tertiary-container": "#cccccc",
                        "surface": "#131313",
                        "background": "#131313",
                        "outline-variant": "#3b494c",
                        "on-primary-container": "#005f6d",
                        "error": "#ffb4ab",
                        "surface-bright": "#393939",
                        "primary-fixed": "#a5eeff",
                        "surface-container-high": "#2a2a2a",
                        "on-background": "#e5e2e1",
                        "surface-container-lowest": "#0e0e0e",
                        "secondary-fixed-dim": "#dfb7ff",
                        "surface-container": "#201f1f",
                        "on-tertiary-container": "#565656",
                        "on-tertiary-fixed-variant": "#474747",
                        "on-error-container": "#ffdad6",
                        "secondary-fixed": "#f1daff",
                        "inverse-surface": "#e5e2e1",
                        "on-tertiary-fixed": "#1b1b1b",
                        "on-secondary": "#4b007e",
                        "on-error": "#690005",
                        "surface-dim": "#131313",
                        "tertiary-fixed-dim": "#c6c6c6",
                        "outline": "#859397",
                        "on-secondary-container": "#f7e6ff",
                        "tertiary-fixed": "#e2e2e2",
                        "error-container": "#93000a",
                        "on-secondary-fixed-variant": "#6b00b0",
                        "inverse-primary": "#006877"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    "spacing": {
                        "stack-gap": "24px",
                        "gutter-desktop": "32px",
                        "container-padding-desktop": "64px",
                        "unit": "8px",
                        "gutter-mobile": "16px",
                        "container-padding-mobile": "24px",
                        "card-padding-internal": "32px"
                    },
                    "fontFamily": {
                        "headline-md": ["Sora"],
                        "body-md": ["Geist"],
                        "headline-xl": ["Sora"],
                        "label-sm": ["JetBrains Mono"],
                        "headline-lg": ["Sora"],
                        "label-md": ["JetBrains Mono"],
                        "body-lg": ["Geist"]
                    },
                    "fontSize": {
                        "headline-md": ["24px", {"lineHeight": "32px", "fontWeight": "600"}],
                        "body-md": ["16px", {"lineHeight": "24px", "fontWeight": "400"}],
                        "headline-xl": ["48px", {"lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700"}],
                        "label-sm": ["10px", {"lineHeight": "14px", "letterSpacing": "0.08em", "fontWeight": "600"}],
                        "headline-lg": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.01em", "fontWeight": "600"}],
                        "label-md": ["12px", {"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "500"}],
                        "body-lg": ["18px", {"lineHeight": "28px", "fontWeight": "400"}]
                    }
                }
            }
        }
    </script>
</head>
<body class="font-body-md text-on-surface bg-background selection:bg-primary-fixed-dim selection:text-on-primary-fixed">
<!-- Side Navigation Bar (From JSON) -->
<nav class="fixed left-0 top-0 h-full flex flex-col py-8 z-40 bg-surface-container-lowest border-r border-white/10 shadow-2xl shadow-black w-64 md:flex hidden">
<div class="px-6 mb-12">
<h1 class="text-headline-lg font-headline-lg text-primary-fixed-dim tracking-tight">Aura Core</h1>
<div class="flex items-center gap-2 mt-2">
<span class="w-2 h-2 rounded-full bg-primary-fixed-dim animate-pulse"></span>
<span class="text-label-md font-label-md text-on-surface-variant uppercase tracking-widest">Automation Active</span>
</div>
</div>
<div class="flex-1 space-y-2">
<!-- Nav Item: Dashboard -->
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined">dashboard</span>
<span class="font-label-md text-label-md">Dashboard</span>
</a>
<!-- Nav Item: Automations -->
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined">bolt</span>
<span class="font-label-md text-label-md">Automations</span>
</a>
<!-- Nav Item: Chat -->
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined">chat_bubble</span>
<span class="font-label-md text-label-md">Chat</span>
</a>
<!-- Nav Item: Calendar -->
<a class="text-on-surface-variant flex items-center gap-3 px-6 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all duration-200 hover:translate-x-1" href="#">
<span class="material-symbols-outlined">calendar_today</span>
<span class="font-label-md text-label-md">Calendar</span>
</a>
<!-- Nav Item: Analytics (Active State applied to represent Security/Analytics focus) -->
<a class="text-primary-fixed-dim font-bold border-r-2 border-primary-fixed-dim pr-4 flex items-center gap-3 px-6 py-3 hover:bg-white/5 transition-all duration-200" href="#">
<span class="material-symbols-outlined">analytics</span>
<span class="font-label-md text-label-md">Analytics</span>
</a>
</div>
<div class="px-6 mt-auto space-y-4">
<button class="w-full obsidian-gradient text-on-primary-fixed py-3 rounded-lg font-label-md text-label-md hover:opacity-90 transition-opacity active:scale-95 duration-150">
                New Task
            </button>
<div class="pt-6 border-t border-white/5 space-y-2">
<a class="text-on-surface-variant flex items-center gap-3 py-2 hover:text-primary-fixed-dim transition-colors" href="#">
<span class="material-symbols-outlined">help</span>
<span class="font-label-md text-label-md">Help</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 py-2 hover:text-error transition-colors" href="#">
<span class="material-symbols-outlined">logout</span>
<span class="font-label-md text-label-md">Sign Out</span>
</a>
</div>
</div>
</nav>
<!-- Main Content Canvas -->
<main class="md:ml-64 min-h-screen">
<!-- Top App Bar -->
<header class="sticky top-0 z-30 flex items-center justify-between px-gutter-desktop h-16 w-full backdrop-blur-md bg-background/80 border-b border-white/10">
<div class="flex items-center gap-4">
<span class="material-symbols-outlined text-primary-fixed-dim md:hidden">menu</span>
<h2 class="text-headline-md font-headline-md text-primary-fixed-dim">Security Log</h2>
</div>
<div class="flex items-center gap-6">
<div class="hidden lg:flex items-center bg-surface-container-low border border-white/10 rounded-full px-4 py-1 gap-3">
<span class="material-symbols-outlined text-on-surface-variant text-sm">search</span>
<input class="bg-transparent border-none focus:ring-0 text-body-sm w-48 text-on-surface" placeholder="Search events..." type="text"/>
</div>
<div class="flex items-center gap-4">
<span class="material-symbols-outlined text-on-surface-variant hover:text-primary-fixed-dim cursor-pointer transition-colors">notifications</span>
<span class="material-symbols-outlined text-on-surface-variant hover:text-primary-fixed-dim cursor-pointer transition-colors">settings</span>
<div class="w-8 h-8 rounded-full bg-surface-container-highest border border-white/20 overflow-hidden">
<img class="w-full h-full object-cover" data-alt="A futuristic professional portrait of a tech-savvy user in a high-contrast dark room with subtle cyan rim lighting, dressed in sleek obsidian-colored attire, conveying a sense of elite digital security management. The background is slightly blurred with soft bokeh from digital displays." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDdA3r45uYjeG5XpZCLp8j0kAHkpwKPygBCPbQqELIZ_Q9W1Waxj5keHBcHH39pd-VRe_VuN9c3v9Q9-ZzXhmEDsOEd_0WGRZ86gBySUK645DaxBpPr8r6dMu1BCPx6amyE3cFj0tYQzBo4sq3YBfhkHut_h_TNAb7vqhl9gVABNNjnUriawGJEKuDD32wjSOSnQ4OCTZ7zbDBo3282DNZGdCJdcR18T2yTSH2vV7KmRZUb8EiCx4JVw8rg5TuSYoBM4IGivRreGD0"/>
</div>
</div>
</div>
</header>
<div class="p-container-padding-desktop max-w-7xl mx-auto space-y-stack-gap">
<!-- Quick Actions & Status Summary -->
<section class="grid grid-cols-1 lg:grid-cols-12 gap-stack-gap">
<!-- Status Summary -->
<div class="lg:col-span-8 glass-panel rounded-xl p-card-padding-internal flex items-center justify-between overflow-hidden relative group">

<div class="relative z-10">
<p class="text-label-md font-label-md text-on-surface-variant uppercase tracking-tighter">System Health</p>
<h3 class="text-headline-lg font-headline-lg mt-1">All Systems Nominal</h3>
<p class="text-body-md text-on-surface-variant mt-2 max-w-md">Perimeter secured. 24 active sensors monitored. No unauthorized attempts in the last 72 hours.</p>
</div>
<div class="relative z-10 hidden sm:flex h-24 w-24 items-center justify-center border-2 border-primary-fixed-dim/30 rounded-full">
<span class="material-symbols-outlined text-primary-fixed-dim text-4xl animate-pulse">verified_user</span>
</div>
</div>
<!-- Emergency Controls -->
<div class="lg:col-span-4 flex flex-col gap-4">
<button class="flex-1 glass-panel hover:bg-surface-container-high transition-all duration-300 group rounded-xl p-4 flex items-center gap-4 border-white/10 border active:scale-95">
<div class="w-12 h-12 rounded-lg bg-surface-container-highest flex items-center justify-center text-primary-fixed-dim">
<span class="material-symbols-outlined">lock</span>
</div>
<div class="text-left">
<p class="font-headline-md text-lg leading-tight">Lock All</p>
<p class="text-label-md font-label-md text-on-surface-variant">Seal all entry points</p>
</div>
</button>
<button class="flex-1 bg-error-container/20 border border-error/30 hover:bg-error-container/40 transition-all duration-300 group rounded-xl p-4 flex items-center gap-4 active:scale-95 neon-glow-error">
<div class="w-12 h-12 rounded-lg bg-error/20 flex items-center justify-center text-error">
<span class="material-symbols-outlined animate-ping">report</span>
</div>
<div class="text-left">
<p class="font-headline-md text-lg text-error leading-tight">Panic Mode</p>
<p class="text-label-md font-label-md text-error/60">Alert authorities immediately</p>
</div>
</button>
</div>
</section>
<!-- Main Layout: Live Feed & Log -->
<section class="grid grid-cols-1 lg:grid-cols-3 gap-stack-gap">
<!-- Security Log List -->
<div class="lg:col-span-2 space-y-4">
<div class="flex items-center justify-between mb-4">
<h4 class="text-headline-md font-headline-md">Recent Activity</h4>
<button class="text-label-md font-label-md text-primary-fixed-dim hover:underline uppercase tracking-widest">Filter By Type</button>
</div>
<!-- Log Items -->
<div class="space-y-3">
<!-- Log Entry 1 -->
<div class="glass-panel hover:bg-white/5 transition-all p-4 rounded-xl flex items-center gap-4 group cursor-pointer">
<div class="w-10 h-10 rounded-full bg-secondary-container/20 flex items-center justify-center text-secondary-fixed-dim">
<span class="material-symbols-outlined">person_check</span>
</div>
<div class="flex-1">
<p class="text-body-md font-bold">Access Granted</p>
<p class="text-label-md font-label-md text-on-surface-variant">Front Door Portal • Primary Resident</p>
</div>
<div class="text-right flex flex-col items-end gap-2">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase">14:22:05</span>
<span class="px-3 py-0.5 rounded-full bg-primary-fixed-dim/10 text-primary-fixed-dim text-[10px] font-bold uppercase tracking-wider border border-primary-fixed-dim/20">Authorized</span>
</div>
</div>
<!-- Log Entry 2 -->
<div class="glass-panel hover:bg-white/5 transition-all p-4 rounded-xl flex items-center gap-4 group cursor-pointer">
<div class="w-10 h-10 rounded-full bg-primary-fixed-dim/10 flex items-center justify-center text-primary-fixed-dim">
<span class="material-symbols-outlined">motion_sense</span>
</div>
<div class="flex-1">
<p class="text-body-md font-bold">Motion Detected</p>
<p class="text-label-md font-label-md text-on-surface-variant">North Garden Zone • Camera 04</p>
</div>
<div class="text-right flex flex-col items-end gap-2">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase">13:45:12</span>
<span class="px-3 py-0.5 rounded-full bg-secondary-container/10 text-secondary-fixed-dim text-[10px] font-bold uppercase tracking-wider border border-secondary-container/20">Flagged</span>
</div>
</div>
<!-- Log Entry 3 -->
<div class="glass-panel hover:bg-white/5 transition-all p-4 rounded-xl flex items-center gap-4 group cursor-pointer">
<div class="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center text-on-surface-variant">
<span class="material-symbols-outlined">lock</span>
</div>
<div class="flex-1">
<p class="text-body-md font-bold">Door Locked</p>
<p class="text-label-md font-label-md text-on-surface-variant">Side Garage Entry • Auto-Relock</p>
</div>
<div class="text-right flex flex-col items-end gap-2">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase">12:30:00</span>
<span class="px-3 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant text-[10px] font-bold uppercase tracking-wider border border-white/10">Standard</span>
</div>
</div>
<!-- Log Entry 4 -->
<div class="glass-panel hover:bg-white/5 transition-all p-4 rounded-xl flex items-center gap-4 group cursor-pointer">
<div class="w-10 h-10 rounded-full bg-error-container/20 flex items-center justify-center text-error">
<span class="material-symbols-outlined">error</span>
</div>
<div class="flex-1">
<p class="text-body-md font-bold">Failed Login Attempt</p>
<p class="text-label-md font-label-md text-on-surface-variant">Smart Hub Interface • IP: 192.168.1.144</p>
</div>
<div class="text-right flex flex-col items-end gap-2">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase">11:15:33</span>
<span class="px-3 py-0.5 rounded-full bg-error-container/30 text-error text-[10px] font-bold uppercase tracking-wider border border-error/50">Rejected</span>
</div>
</div>
<!-- Log Entry 5 -->
<div class="glass-panel hover:bg-white/5 transition-all p-4 rounded-xl flex items-center gap-4 group cursor-pointer">
<div class="w-10 h-10 rounded-full bg-primary-fixed-dim/10 flex items-center justify-center text-primary-fixed-dim">
<span class="material-symbols-outlined">refresh</span>
</div>
<div class="flex-1">
<p class="text-body-md font-bold">Routine Diagnostic</p>
<p class="text-label-md font-label-md text-on-surface-variant">Central Core • Periodic Checksum Pass</p>
</div>
<div class="text-right flex flex-col items-end gap-2">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase">10:00:00</span>
<span class="px-3 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant text-[10px] font-bold uppercase tracking-wider border border-white/10">System</span>
</div>
</div>
</div>
<button class="w-full py-4 glass-panel hover:bg-white/5 transition-colors text-label-md font-label-md text-on-surface-variant rounded-xl border-dashed border-white/20 border">
                        Load Older History
                    </button>
</div>
<!-- Live Feed & Sidebar Widgets -->
<div class="space-y-stack-gap">
<!-- Live Feed Widget -->
<div class="glass-panel rounded-xl overflow-hidden flex flex-col group">
<div class="relative aspect-video bg-black overflow-hidden">
<img class="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-700" data-alt="A cinematic security camera view of a modern minimalist living room at night. The room features sharp architectural lines, a dark velvet sofa, and a single designer lamp casting dramatic shadows. The image has a subtle digital scanline overlay and a small 'LIVE' indicator in neon cyan at the corner. High-performance, luxury smart home vibe." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAfsb-uEFZVtnfbCVEyKkGy-p2Q5ieGk9zpXTuLbeG6VI2PwMQ3-OUvnEh1lceWZdlHJeniyivOPG5O7928NZdjBaiZTLXCMarbQL-0YpmB0jsU4blTxgd6pL52TqY-4b9Wj5cSea2QhXdO2pDdmmkEtyWx12usSHFvKOFETR6dcNlalj_Rg8n80awZ3zwViWM2OeXh_6dsVrvnQm5qo5qsn1L12Xtqg4vB9alUfXM-yuwZ1P9KIyB6l2H5dxqL0GNtZlA23WpwFK0"/>
<div class="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent flex flex-col justify-between p-4">
<div class="flex items-center justify-between">
<div class="flex items-center gap-2 bg-black/60 px-2 py-1 rounded-md border border-primary-fixed-dim/30">
<span class="w-2 h-2 rounded-full bg-red-600 animate-pulse"></span>
<span class="text-label-sm font-label-sm text-on-surface tracking-tighter">LIVE • CAM 01</span>
</div>
<span class="material-symbols-outlined text-on-surface text-sm">fullscreen</span>
</div>
<div class="flex items-center justify-between">
<p class="text-label-sm font-label-sm text-on-surface/70">Main Entrance Hall</p>
<p class="text-label-sm font-label-sm text-on-surface/70" id="live-timer">00:00:00</p>
</div>
</div>
</div>
<div class="p-4 flex gap-2 overflow-x-auto no-scrollbar">
<button class="shrink-0 w-16 h-10 rounded bg-primary-fixed-dim/10 border border-primary-fixed-dim flex items-center justify-center">
<span class="material-symbols-outlined text-primary-fixed-dim">videocam</span>
</button>
<button class="shrink-0 w-16 h-10 rounded bg-white/5 border border-white/10 flex items-center justify-center opacity-50 hover:opacity-100 transition-opacity">
<span class="material-symbols-outlined text-white text-sm">nest_cam_wired_stand</span>
</button>
<button class="shrink-0 w-16 h-10 rounded bg-white/5 border border-white/10 flex items-center justify-center opacity-50 hover:opacity-100 transition-opacity">
<span class="material-symbols-outlined text-white text-sm">door_sensor</span>
</button>
<button class="shrink-0 w-16 h-10 rounded bg-white/5 border border-white/10 flex items-center justify-center opacity-50 hover:opacity-100 transition-opacity">
<span class="material-symbols-outlined text-white text-sm">yard</span>
</button>
</div>
</div>
<!-- Security Insights -->
<div class="glass-panel rounded-xl p-card-padding-internal space-y-4">
<h4 class="text-label-md font-label-md text-on-surface-variant uppercase tracking-widest border-b border-white/5 pb-2">Active Threats</h4>
<div class="flex items-center justify-between">
<div class="flex items-center gap-3">
<div class="w-2 h-2 rounded-full bg-primary-fixed-dim"></div>
<span class="text-body-sm">Unrecognized IP</span>
</div>
<span class="text-label-sm font-label-sm bg-surface-container-highest px-2 py-0.5 rounded">Blocked</span>
</div>
<div class="flex items-center justify-between">
<div class="flex items-center gap-3">
<div class="w-2 h-2 rounded-full bg-secondary-fixed-dim"></div>
<span class="text-body-sm">Weak Protocol (IoT)</span>
</div>
<span class="text-label-sm font-label-sm text-primary-fixed-dim">Optimizing</span>
</div>
<div class="mt-4 pt-4 border-t border-white/5">
<button class="w-full obsidian-gradient text-on-primary-fixed py-2 rounded font-label-md text-label-md hover:scale-[1.02] transition-transform">
                                Run Full Scan
                            </button>
</div>
</div>
<!-- Environment Stats -->
<div class="grid grid-cols-2 gap-4">
<div class="glass-panel p-4 rounded-xl">
<p class="text-label-sm font-label-sm text-on-surface-variant">Sensors</p>
<p class="text-headline-md font-headline-md text-primary-fixed-dim mt-1">24/24</p>
</div>
<div class="glass-panel p-4 rounded-xl">
<p class="text-label-sm font-label-sm text-on-surface-variant">Uptime</p>
<p class="text-headline-md font-headline-md text-primary-fixed-dim mt-1">100%</p>
</div>
</div>
</div>
</section>
</div>
</main>
<script>
        // Simple script for updating the live feed timer
        function updateLiveTimer() {
            const timerElement = document.getElementById('live-timer');
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            timerElement.textContent = `${h}:${m}:${s}`;
        }
        setInterval(updateLiveTimer, 1000);
        updateLiveTimer();

        // Micro-interactions for the list items
        document.querySelectorAll('.glass-panel').forEach(panel => {
            panel.addEventListener('mousedown', () => panel.classList.add('scale-95'));
            panel.addEventListener('mouseup', () => panel.classList.remove('scale-95'));
            panel.addEventListener('mouseleave', () => panel.classList.remove('scale-95'));
        });
    </script>
</body></html>




--------------------------------------------------------------------------------------------------------------------------------------









# Dashboard, mostra o geral

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Aura Assist - Automation Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700&amp;family=Geist:wght@400&amp;family=JetBrains+Mono:wght@500;600&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<script id="tailwind-config">
        tailwind.config = {
          darkMode: "class",
          theme: {
            extend: {
              "colors": {
                      "secondary": "#dfb7ff",
                      "on-error": "#690005",
                      "primary": "#baf2ff",
                      "tertiary-fixed": "#e2e2e2",
                      "on-tertiary-fixed": "#1b1b1b",
                      "on-tertiary-container": "#565656",
                      "outline-variant": "#3b494c",
                      "primary-fixed-dim": "#00daf8",
                      "inverse-on-surface": "#313030",
                      "error-container": "#93000a",
                      "surface-bright": "#393939",
                      "error": "#ffb4ab",
                      "surface-container-high": "#2a2a2a",
                      "inverse-primary": "#006877",
                      "surface": "#131313",
                      "inverse-surface": "#e5e2e1",
                      "primary-container": "#00e0ff",
                      "surface-container-lowest": "#0e0e0e",
                      "secondary-fixed-dim": "#dfb7ff",
                      "on-primary-fixed-variant": "#004e5a",
                      "surface-container-low": "#1c1b1b",
                      "on-error-container": "#ffdad6",
                      "surface-tint": "#00daf8",
                      "tertiary-container": "#cccccc",
                      "outline": "#859397",
                      "surface-dim": "#131313",
                      "on-secondary-fixed": "#2d004f",
                      "secondary-container": "#9d05ff",
                      "on-tertiary": "#303030",
                      "on-secondary-container": "#f7e6ff",
                      "on-primary-container": "#005f6d",
                      "on-surface": "#e5e2e1",
                      "tertiary": "#e8e8e8",
                      "secondary-fixed": "#f1daff",
                      "surface-container-highest": "#353534",
                      "on-surface-variant": "#bac9cd",
                      "surface-variant": "#353534",
                      "tertiary-fixed-dim": "#c6c6c6",
                      "on-tertiary-fixed-variant": "#474747",
                      "surface-container": "#201f1f",
                      "on-secondary": "#4b007e",
                      "on-primary": "#00363f",
                      "on-secondary-fixed-variant": "#6b00b0",
                      "on-background": "#e5e2e1",
                      "primary-fixed": "#a5eeff",
                      "background": "#131313",
                      "on-primary-fixed": "#001f25"
              },
              "borderRadius": {
                      "DEFAULT": "0.125rem",
                      "lg": "0.25rem",
                      "xl": "0.5rem",
                      "full": "0.75rem"
              },
              "spacing": {
                      "container-padding-desktop": "64px",
                      "card-padding-internal": "32px",
                      "gutter-desktop": "32px",
                      "gutter-mobile": "16px",
                      "container-padding-mobile": "24px",
                      "unit": "8px",
                      "stack-gap": "24px"
              },
              "fontFamily": {
                      "headline-md": [
                              "Sora"
                      ],
                      "label-sm": [
                              "JetBrains Mono"
                      ],
                      "body-lg": [
                              "Geist"
                      ],
                      "headline-lg-mobile": [
                              "Sora"
                      ],
                      "body-md": [
                              "Geist"
                      ],
                      "label-md": [
                              "JetBrains Mono"
                      ],
                      "body-sm": [
                              "Geist"
                      ],
                      "headline-xl": [
                              "Sora"
                      ],
                      "headline-lg": [
                              "Sora"
                      ]
              },
              "fontSize": {
                      "headline-md": [
                              "24px",
                              {
                                      "lineHeight": "32px",
                                      "fontWeight": "600"
                              }
                      ],
                      "label-sm": [
                              "10px",
                              {
                                      "lineHeight": "14px",
                                      "letterSpacing": "0.08em",
                                      "fontWeight": "600"
                              }
                      ],
                      "body-lg": [
                              "18px",
                              {
                                      "lineHeight": "28px",
                                      "fontWeight": "400"
                              }
                      ],
                      "headline-lg-mobile": [
                              "28px",
                              {
                                      "lineHeight": "36px",
                                      "fontWeight": "600"
                              }
                      ],
                      "body-md": [
                              "16px",
                              {
                                      "lineHeight": "24px",
                                      "fontWeight": "400"
                              }
                      ],
                      "label-md": [
                              "12px",
                              {
                                      "lineHeight": "16px",
                                      "letterSpacing": "0.05em",
                                      "fontWeight": "500"
                              }
                      ],
                      "body-sm": [
                              "14px",
                              {
                                      "lineHeight": "20px",
                                      "fontWeight": "400"
                              }
                      ],
                      "headline-xl": [
                              "48px",
                              {
                                      "lineHeight": "56px",
                                      "letterSpacing": "-0.02em",
                                      "fontWeight": "700"
                              }
                      ],
                      "headline-lg": [
                              "32px",
                              {
                                      "lineHeight": "40px",
                                      "letterSpacing": "-0.01em",
                                      "fontWeight": "600"
                              }
                      ]
              }
            },
          },
        }
    </script>
<style>
        .glowing-text {
            text-shadow: 0 0 15px rgba(0, 218, 248, 0.4);
        }
        .glowing-text-secondary {
            text-shadow: 0 0 15px rgba(223, 183, 255, 0.4);
        }
        .matrix-bg {
            background: radial-gradient(circle at center, rgba(0, 218, 248, 0.05) 0%, transparent 70%);
        }
    </style>
</head>
<body class="bg-background text-on-background font-body-md text-body-md h-screen flex overflow-hidden selection:bg-primary selection:text-on-primary">
<!-- SideNavBar (Desktop) -->
<nav class="hidden md:flex flex-col w-64 h-screen fixed left-0 top-0 py-8 z-40 bg-surface-container-lowest border-r border-white/10 shadow-2xl shadow-black transition-transform duration-200">
<div class="px-6 mb-12 flex items-center gap-4">
<div class="w-10 h-10 rounded-full bg-surface-container-high border border-white/10 overflow-hidden flex-shrink-0">
<img alt="Assistant Avatar" class="w-full h-full object-cover" data-alt="A highly detailed, sleek futuristic 3D avatar headshot of an AI assistant. The avatar features smooth metallic dark gray surfaces with glowing electric blue circuitry lines. Set against a pure black background with high-contrast, moody rim lighting." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAEFmoOT78XSLiBKi78nN5kSjzhetVKayBcQe4_aAtFBFGUyq6KP6Ra4refNFh0Lg13xoJcVfs_DP7esiRoNd1FaxXhY-_iEzzqIuMJ-Rd6-umWq8PZGXGXHM4N3PpvSXgIQeZbhN8urF-C7r-AQvtjxsvvelq1KZPO8UbiGpVcrNWck8XgMAcESLR52wyqP6QfrogrlpRu6TXz8WyIkNSb77kMZuDprRICF4nHOtgagny2I-5Z_JsnL1Q7lk_H2GE8Bvpa3nuNXJI"/>
</div>
<div>
<h1 class="text-headline-md font-headline-md font-bold text-primary-fixed-dim tracking-tight">Aura Core</h1>
<p class="text-label-sm font-label-sm text-secondary-fixed-dim uppercase tracking-wider mt-1">Automation Active</p>
</div>
</div>
<div class="flex-1 overflow-y-auto px-4 flex flex-col gap-2">
<a class="text-primary-fixed-dim font-bold border-r-2 border-primary-fixed-dim pr-4 bg-white/5 flex items-center gap-3 px-4 py-3 rounded-l-lg hover:bg-white/5 transition-all" href="#">
<span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">dashboard</span>
<span class="text-label-md font-label-md uppercase tracking-wider">Dashboard</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all duration-200" href="#">
<span class="material-symbols-outlined">bolt</span>
<span class="text-label-md font-label-md uppercase tracking-wider">Automations</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all duration-200" href="#">
<span class="material-symbols-outlined">chat_bubble</span>
<span class="text-label-md font-label-md uppercase tracking-wider">Chat</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all duration-200" href="#">
<span class="material-symbols-outlined">calendar_today</span>
<span class="text-label-md font-label-md uppercase tracking-wider">Calendar</span>
</a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/5 hover:text-secondary-fixed-dim hover:translate-x-1 transition-all duration-200" href="#">
<span class="material-symbols-outlined">analytics</span>
<span class="text-label-md font-label-md uppercase tracking-wider">Analytics</span>
</a>
</div>
<div class="px-6 mt-auto">
<button class="w-full py-3 mb-6 bg-gradient-to-r from-surface-container-highest to-surface border border-primary/30 text-white font-label-md text-label-md uppercase tracking-wider rounded-lg shadow-[0_0_15px_rgba(0,218,248,0.15)] hover:shadow-[0_0_20px_rgba(0,218,248,0.3)] hover:border-primary transition-all duration-300 flex items-center justify-center gap-2">
<span class="material-symbols-outlined text-[18px]">add</span>
                New Task
            </button>
<div class="flex flex-col gap-2">
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-2 rounded-lg hover:bg-white/5 hover:text-secondary-fixed-dim transition-all text-label-md font-label-md uppercase tracking-wider" href="#">
<span class="material-symbols-outlined text-[18px]">help</span>
                    Help
                </a>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-2 rounded-lg hover:bg-white/5 hover:text-secondary-fixed-dim transition-all text-label-md font-label-md uppercase tracking-wider" href="#">
<span class="material-symbols-outlined text-[18px]">logout</span>
                    Sign Out
                </a>
</div>
</div>
</nav>
<!-- Main Content Area -->
<main class="flex-1 flex flex-col h-screen overflow-y-auto ml-0 md:ml-64 w-full">
<!-- TopNavBar (Mobile / Content Header) -->
<header class="w-full sticky top-0 z-50 flex items-center justify-between px-gutter-desktop h-16 border-b border-white/10 bg-background/80 backdrop-blur-md shadow-[0_20px_40px_rgba(0,0,0,0.8)]">
<div class="flex items-center gap-4">
<!-- Mobile Menu Trigger -->
<button class="md:hidden text-on-surface-variant hover:text-primary-fixed-dim transition-colors scale-95 active:scale-90 duration-150">
<span class="material-symbols-outlined">menu</span>
</button>
<span class="md:hidden text-headline-md font-headline-md font-bold text-primary-fixed-dim tracking-tight">Aura Assist</span>
</div>
<div class="flex items-center gap-6">
<div class="hidden md:flex items-center bg-surface-container-low border border-white/10 rounded-full px-4 py-1.5 focus-within:border-primary-fixed-dim focus-within:shadow-[0_0_10px_rgba(0,218,248,0.1)] transition-all">
<span class="material-symbols-outlined text-on-surface-variant text-[20px]">search</span>
<input class="bg-transparent border-none focus:ring-0 text-body-sm font-body-sm text-on-background placeholder-on-surface-variant ml-2 w-48" placeholder="Search systems..." type="text"/>
</div>
<button class="text-on-surface-variant hover:text-primary-fixed-dim hover:bg-surface-variant/30 rounded-full p-2 transition-colors scale-95 active:scale-90 duration-150">
<span class="material-symbols-outlined">notifications</span>
</button>
<button class="text-on-surface-variant hover:text-primary-fixed-dim hover:bg-surface-variant/30 rounded-full p-2 transition-colors scale-95 active:scale-90 duration-150">
<span class="material-symbols-outlined">settings</span>
</button>
<div class="w-8 h-8 rounded-full border border-white/20 overflow-hidden cursor-pointer hover:border-primary-fixed-dim transition-colors">
<img alt="User profile" class="w-full h-full object-cover" data-alt="A minimalist high-contrast profile picture showing a silhouette of a person against a vibrant neon purple and cyan gradient background. The style is sleek, modern, and anonymous." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAVeS5A_GfJOSaGVZi7L1MT4HUyRWz-Vyz494AAjqBSTbRjQ--4ufDsiuwUPxQbyAXh8FTFoN0PGSDXaC2tshRT3oGiDL8jXNMD_A_iM2wF4884Ffj-s2vLt2ON00_kcSU1XzaeyaEHsOyNNmnseuti06chQI-CdlCFw0ZObb_Oz_DFv8JqrWbQE1rxLGMKkhCGJpXq7_2KSXWIhKw54V8RX0Jut9DsQaM9RMy9f1myJJ4OtpXC5i4Snx4dafBGY9dY2s62xWABvgo"/>
</div>
</div>
</header>
<!-- Dashboard Content -->
<div class="p-container-padding-mobile md:p-container-padding-desktop flex flex-col gap-stack-gap max-w-[1600px] mx-auto w-full">
<!-- Header Section -->
<div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
<div>
<h2 class="text-headline-xl font-headline-xl font-bold text-white tracking-tight mb-2">Systems Online</h2>
<p class="text-body-lg font-body-lg text-on-surface-variant">All automation nodes operating within optimal parameters.</p>
</div>
<div class="flex items-center gap-3">
<span class="flex h-3 w-3 relative">
<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-fixed-dim opacity-75"></span>
<span class="relative inline-flex rounded-full h-3 w-3 bg-primary-fixed-dim"></span>
</span>
<span class="text-label-md font-label-md text-primary-fixed-dim uppercase tracking-wider glowing-text">Live Sync</span>
</div>
</div>
<!-- Bento Grid -->
<div class="grid grid-cols-1 md:grid-cols-12 gap-8 mt-4">
<!-- Active Flow Matrix (Hero Card) -->
<div class="md:col-span-8 bg-surface-container border border-white/10 rounded-xl p-card-padding-internal shadow-[0_20px_40px_rgba(0,0,0,0.8)] relative overflow-hidden group">
<div class="absolute inset-0 matrix-bg opacity-50 z-0"></div>
<div class="relative z-10 flex flex-col h-full min-h-[360px]">
<div class="flex items-center justify-between mb-6">
<h3 class="text-headline-md font-headline-md font-semibold text-white">Active Flow Matrix</h3>
<button class="text-primary-fixed-dim hover:text-white transition-colors">
<span class="material-symbols-outlined">open_in_full</span>
</button>
</div>
<div class="flex-1 w-full rounded-lg border border-white/5 bg-surface-container-lowest/50 relative overflow-hidden backdrop-blur-sm flex items-center justify-center">
<!-- Placeholder for Data Viz / Canvas -->
<div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMSIgZmlsbD0icmdiYSgyNTUsMjU1LDI1NSwwLjEpIi8+PC9zdmc+')] opacity-30"></div>
<div class="relative z-10 flex items-center gap-8">
<div class="w-16 h-16 rounded-full border border-secondary-fixed-dim/50 flex items-center justify-center shadow-[0_0_20px_rgba(223,183,255,0.2)]">
<span class="material-symbols-outlined text-secondary-fixed-dim text-3xl">sensors</span>
</div>
<div class="w-24 h-px bg-gradient-to-r from-secondary-fixed-dim/50 to-primary-fixed-dim/50 relative">
<div class="absolute w-2 h-2 bg-white rounded-full top-1/2 -translate-y-1/2 -left-1 animate-ping"></div>
</div>
<div class="w-20 h-20 rounded-full border border-primary-fixed-dim bg-primary-fixed-dim/10 flex items-center justify-center shadow-[0_0_30px_rgba(0,218,248,0.3)]">
<span class="material-symbols-outlined text-primary-fixed-dim text-4xl">memory</span>
</div>
<div class="w-24 h-px bg-gradient-to-r from-primary-fixed-dim/50 to-white/20 relative">
<div class="absolute w-2 h-2 bg-white rounded-full top-1/2 -translate-y-1/2 -right-1 animate-ping"></div>
</div>
<div class="w-16 h-16 rounded-full border border-white/20 flex items-center justify-center bg-surface">
<span class="material-symbols-outlined text-on-surface-variant text-3xl">cloud_sync</span>
</div>
</div>
</div>
<div class="mt-6 flex items-center gap-6 text-label-md font-label-md text-on-surface-variant uppercase tracking-wider">
<div class="flex items-center gap-2">
<div class="w-2 h-2 rounded-full bg-secondary-fixed-dim"></div>
                                Input Nodes
                            </div>
<div class="flex items-center gap-2">
<div class="w-2 h-2 rounded-full bg-primary-fixed-dim"></div>
                                Core Processor
                            </div>
<div class="flex items-center gap-2">
<div class="w-2 h-2 rounded-full bg-white/40"></div>
                                Edge Sync
                            </div>
</div>
</div>
</div>
<!-- Security Status -->
<div class="md:col-span-4 bg-surface-container border border-white/10 rounded-xl p-card-padding-internal shadow-[0_20px_40px_rgba(0,0,0,0.8)] flex flex-col justify-between">
<div>
<div class="flex items-center justify-between mb-4">
<h3 class="text-headline-md font-headline-md font-semibold text-white">Security</h3>
<span class="material-symbols-outlined text-primary-fixed-dim">shield_locked</span>
</div>
<p class="text-body-md font-body-md text-on-surface-variant mb-8">Perimeter defense and internal surveillance systems active.</p>
</div>
<div class="flex flex-col gap-4">
<div class="bg-surface-container-low border border-white/5 rounded-lg p-4 flex items-center justify-between">
<div class="flex items-center gap-3">
<span class="material-symbols-outlined text-secondary-fixed-dim">nest_cam_indoor</span>
<span class="text-body-md font-body-md text-inverse-surface">Cameras</span>
</div>
<span class="text-label-md font-label-md bg-secondary-fixed-dim text-black px-2 py-1 rounded">12 ONLINE</span>
</div>
<div class="bg-surface-container-low border border-white/5 rounded-lg p-4 flex items-center justify-between">
<div class="flex items-center gap-3">
<span class="material-symbols-outlined text-primary-fixed-dim">door_front</span>
<span class="text-body-md font-body-md text-inverse-surface">Access Points</span>
</div>
<span class="text-label-md font-label-md bg-primary-fixed-dim text-black px-2 py-1 rounded">LOCKED</span>
</div>
</div>
</div>
<!-- Lighting Zones -->
<div class="md:col-span-6 bg-surface-container border border-white/10 rounded-xl p-card-padding-internal shadow-[0_20px_40px_rgba(0,0,0,0.8)]">
<div class="flex items-center justify-between mb-6">
<h3 class="text-headline-md font-headline-md font-semibold text-white">Lighting Zones</h3>
<span class="material-symbols-outlined text-secondary-fixed-dim">lightbulb</span>
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
<!-- Zone 1 -->
<div class="bg-surface-container-low border border-secondary-fixed-dim/30 rounded-lg p-5 flex flex-col gap-4 hover:border-secondary-fixed-dim/60 transition-colors shadow-[0_0_15px_rgba(223,183,255,0.05)]">
<div class="flex justify-between items-center">
<span class="text-body-md font-body-md font-medium text-white">Main Studio</span>
<!-- Toggle placeholder -->
<div class="w-10 h-5 bg-secondary-fixed-dim rounded-full relative cursor-pointer">
<div class="absolute right-1 top-1 w-3 h-3 bg-black rounded-full"></div>
</div>
</div>
<div class="w-full h-1 bg-surface-bright rounded-full overflow-hidden">
<div class="h-full bg-secondary-fixed-dim w-[80%] shadow-[0_0_10px_rgba(223,183,255,0.8)]"></div>
</div>
<div class="text-label-sm font-label-sm text-secondary-fixed-dim text-right">80% INTENSITY</div>
</div>
<!-- Zone 2 -->
<div class="bg-surface-container-lowest border border-white/5 rounded-lg p-5 flex flex-col gap-4">
<div class="flex justify-between items-center">
<span class="text-body-md font-body-md font-medium text-on-surface-variant">Corridors</span>
<div class="w-10 h-5 bg-surface-bright rounded-full relative cursor-pointer">
<div class="absolute left-1 top-1 w-3 h-3 bg-on-surface-variant rounded-full"></div>
</div>
</div>
<div class="w-full h-1 bg-surface-bright rounded-full overflow-hidden">
<div class="h-full bg-on-surface-variant w-[20%]"></div>
</div>
<div class="text-label-sm font-label-sm text-on-surface-variant text-right">20% INTENSITY</div>
</div>
</div>
</div>
<!-- Climate Zones -->
<div class="md:col-span-6 bg-surface-container border border-white/10 rounded-xl p-card-padding-internal shadow-[0_20px_40px_rgba(0,0,0,0.8)]">
<div class="flex items-center justify-between mb-6">
<h3 class="text-headline-md font-headline-md font-semibold text-white">Climate Control</h3>
<span class="material-symbols-outlined text-primary-fixed-dim">thermostat</span>
</div>
<div class="flex items-center gap-8 h-full pb-4">
<div class="flex flex-col items-center justify-center bg-surface-container-lowest border border-primary-fixed-dim/20 w-32 h-32 rounded-full relative shadow-[0_0_20px_rgba(0,218,248,0.1)]">
<svg class="absolute inset-0 w-full h-full rotate-90" viewbox="0 0 100 100">
<circle cx="50" cy="50" fill="none" r="45" stroke="rgba(255,255,255,0.05)" stroke-dasharray="280" stroke-dashoffset="0" stroke-width="4"></circle>
<circle cx="50" cy="50" fill="none" r="45" stroke="#00daf8" stroke-dasharray="280" stroke-dashoffset="80" stroke-width="4"></circle>
</svg>
<span class="text-headline-lg font-headline-lg font-bold text-white z-10">72°</span>
<span class="text-label-sm font-label-sm text-primary-fixed-dim uppercase z-10 mt-1">Target</span>
</div>
<div class="flex-1 flex flex-col gap-4">
<div class="flex justify-between items-end border-b border-white/5 pb-2">
<div class="flex flex-col">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase mb-1">Server Room</span>
<span class="text-body-lg font-body-lg text-primary-fixed-dim glowing-text">64°F</span>
</div>
<span class="material-symbols-outlined text-primary-fixed-dim text-sm">ac_unit</span>
</div>
<div class="flex justify-between items-end border-b border-white/5 pb-2">
<div class="flex flex-col">
<span class="text-label-sm font-label-sm text-on-surface-variant uppercase mb-1">Office Floor</span>
<span class="text-body-lg font-body-lg text-inverse-surface">71°F</span>
</div>
<span class="material-symbols-outlined text-on-surface-variant text-sm">air</span>
</div>
</div>
</div>
</div>
</div>
</div>
</main>
</body></html>






--------------------------------------------------------------------------------------------------------------------------------------







# Configurações

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Settings - Aura Assist</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&amp;family=Geist:wght@400;500&amp;family=JetBrains+Mono:wght@500;600&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<style>
        .material-symbols-outlined {
            font-family: 'Material Symbols Outlined';
            font-weight: normal;
            font-style: normal;
            font-size: 24px;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-feature-settings: 'liga';
            -webkit-font-smoothing: antialiased;
        }
        
        body {
            background-color: #131313;
        }
        
        .glow-accent:hover {
            box-shadow: 0 0 15px rgba(0, 218, 248, 0.2);
        }
    </style>
<script id="tailwind-config">
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            "colors": {
                    "secondary": "#dfb7ff",
                    "on-error": "#690005",
                    "primary": "#baf2ff",
                    "tertiary-fixed": "#e2e2e2",
                    "on-tertiary-fixed": "#1b1b1b",
                    "on-tertiary-container": "#565656",
                    "outline-variant": "#3b494c",
                    "primary-fixed-dim": "#00daf8",
                    "inverse-on-surface": "#313030",
                    "error-container": "#93000a",
                    "surface-bright": "#393939",
                    "error": "#ffb4ab",
                    "surface-container-high": "#2a2a2a",
                    "inverse-primary": "#006877",
                    "surface": "#131313",
                    "inverse-surface": "#e5e2e1",
                    "primary-container": "#00e0ff",
                    "surface-container-lowest": "#0e0e0e",
                    "secondary-fixed-dim": "#dfb7ff",
                    "on-primary-fixed-variant": "#004e5a",
                    "surface-container-low": "#1c1b1b",
                    "on-error-container": "#ffdad6",
                    "surface-tint": "#00daf8",
                    "tertiary-container": "#cccccc",
                    "outline": "#859397",
                    "surface-dim": "#131313",
                    "on-secondary-fixed": "#2d004f",
                    "secondary-container": "#9d05ff",
                    "on-tertiary": "#303030",
                    "on-secondary-container": "#f7e6ff",
                    "on-primary-container": "#005f6d",
                    "on-surface": "#e5e2e1",
                    "tertiary": "#e8e8e8",
                    "secondary-fixed": "#f1daff",
                    "surface-container-highest": "#353534",
                    "on-surface-variant": "#bac9cd",
                    "surface-variant": "#353534",
                    "tertiary-fixed-dim": "#c6c6c6",
                    "on-tertiary-fixed-variant": "#474747",
                    "surface-container": "#201f1f",
                    "on-secondary": "#4b007e",
                    "on-primary": "#00363f",
                    "on-secondary-fixed-variant": "#6b00b0",
                    "on-background": "#e5e2e1",
                    "primary-fixed": "#a5eeff",
                    "background": "#131313",
                    "on-primary-fixed": "#001f25"
            },
            "borderRadius": {
                    "DEFAULT": "0.125rem",
                    "lg": "0.25rem",
                    "xl": "0.5rem",
                    "full": "0.75rem"
            },
            "spacing": {
                    "container-padding-desktop": "64px",
                    "card-padding-internal": "32px",
                    "gutter-desktop": "32px",
                    "gutter-mobile": "16px",
                    "container-padding-mobile": "24px",
                    "unit": "8px",
                    "stack-gap": "24px"
            },
            "fontFamily": {
                    "headline-md": ["Sora"],
                    "label-sm": ["JetBrains Mono"],
                    "body-lg": ["Geist"],
                    "headline-lg-mobile": ["Sora"],
                    "body-md": ["Geist"],
                    "label-md": ["JetBrains Mono"],
                    "body-sm": ["Geist"],
                    "headline-xl": ["Sora"],
                    "headline-lg": ["Sora"]
            },
            "fontSize": {
                    "headline-md": ["24px", {"lineHeight": "32px", "fontWeight": "600"}],
                    "label-sm": ["10px", {"lineHeight": "14px", "letterSpacing": "0.08em", "fontWeight": "600"}],
                    "body-lg": ["18px", {"lineHeight": "28px", "fontWeight": "400"}],
                    "headline-lg-mobile": ["28px", {"lineHeight": "36px", "fontWeight": "600"}],
                    "body-md": ["16px", {"lineHeight": "24px", "fontWeight": "400"}],
                    "label-md": ["12px", {"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "500"}],
                    "body-sm": ["14px", {"lineHeight": "20px", "fontWeight": "400"}],
                    "headline-xl": ["48px", {"lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700"}],
                    "headline-lg": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.01em", "fontWeight": "600"}]
            }
          }
        }
      }
    </script>
</head>
<body class="bg-background text-on-background min-h-screen font-body-md text-body-md overflow-x-hidden flex selection:bg-primary-fixed-dim selection:text-black">
<!-- SideNavBar -->
<nav class="hidden md:flex flex-col py-8 z-40 bg-surface-container-lowest border-r border-white/10 w-64 h-screen fixed left-0 top-0 shadow-2xl shadow-black text-secondary-fixed-dim justify-between">
<div class="px-6 flex flex-col gap-8">
<div class="flex items-center gap-4">
<div class="w-10 h-10 rounded-xl bg-surface-container-high border border-white/10 flex items-center justify-center overflow-hidden">
<img class="w-full h-full object-cover" data-alt="A futuristic geometric avatar featuring glowing holographic elements against a deep pure black background. Cinematic high-contrast lighting with subtle neon blue accents. Premium luxury technology aesthetic." src="https://lh3.googleusercontent.com/aida-public/AB6AXuD8xGh6joDO5RM2PX4wJHFwlcwk_d2AR4VgX98fPezTG_wr80eKFKaa6uh2jRj39Ag-IWFgdHvW5YvnLCk-GqXQdATuwBlXTr92-ZnkKAgrDr9C9Tp02WI8XMr6PuiHFxg_nOnrwdoXro_QH-rnqV24fuCGTy5DiBt9cb3ZvpD9I9MQp0ghICKGgBFzk7X5fJq4Z58sKShychNnLdpQ30KgoYZmfaLOcjgxEIvLtRPqZwWgofRIv0BTkf4npl5JRtg4x4E0FH44qbc"/>
</div>
<div>
<h1 class="text-headline-md font-headline-md text-primary-fixed-dim tracking-tight">Aura Core</h1>
<p class="text-label-sm font-label-sm text-on-surface-variant uppercase">Automation Active</p>
</div>
</div>
<button class="w-full py-3 bg-gradient-to-r from-surface-container-highest to-surface-container-lowest border border-white/20 rounded-lg text-on-surface hover:text-primary-fixed-dim transition-all glow-accent flex items-center justify-center gap-2 font-label-md text-label-md">
<span class="material-symbols-outlined" style="font-size: 18px;">add</span>
                New Task
            </button>
<ul class="flex flex-col gap-2">
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">dashboard</span>
                        Dashboard
                    </a>
</li>
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">bolt</span>
                        Automations
                    </a>
</li>
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">chat_bubble</span>
                        Chat
                    </a>
</li>
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">calendar_today</span>
                        Calendar
                    </a>
</li>
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">analytics</span>
                        Analytics
                    </a>
</li>
</ul>
</div>
<ul class="flex flex-col gap-2 px-6">
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">help</span>
                    Help
                </a>
</li>
<li>
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200 rounded-lg font-label-md text-label-md" href="#">
<span class="material-symbols-outlined">logout</span>
                    Sign Out
                </a>
</li>
</ul>
</nav>
<!-- Main Content Canvas -->
<main class="flex-1 md:ml-64 flex flex-col min-h-screen">
<!-- TopNavBar -->
<header class="sticky top-0 z-50 flex items-center justify-between px-gutter-desktop w-full h-16 backdrop-blur-md bg-background/80 shadow-[0_20px_40px_rgba(0,0,0,0.8)] border-b border-white/10">
<div class="flex items-center gap-6">
<!-- Mobile Menu Button (Visible only on small screens) -->
<button class="md:hidden text-on-surface-variant hover:text-primary-fixed-dim transition-colors scale-95 active:scale-90 duration-150">
<span class="material-symbols-outlined">menu</span>
</button>
<h2 class="text-headline-md font-headline-md font-bold text-primary-fixed-dim tracking-tight md:hidden">Aura Assist</h2>
</div>
<div class="flex items-center gap-6">
<button class="text-on-surface-variant hover:text-primary-fixed-dim hover:bg-surface-variant/30 transition-colors scale-95 active:scale-90 duration-150 p-2 rounded-full">
<span class="material-symbols-outlined">notifications</span>
</button>
<!-- Active Nav Element in Header for Settings -->
<button class="text-primary-fixed-dim border-b-2 border-primary-fixed-dim transition-colors scale-95 active:scale-90 duration-150 p-2 -mb-[2px]">
<span class="material-symbols-outlined">settings</span>
</button>
<div class="w-8 h-8 rounded-full overflow-hidden border border-white/10 cursor-pointer hover:border-primary-fixed-dim transition-colors">
<img class="w-full h-full object-cover" data-alt="A high-end cinematic profile portrait of a mysterious tech professional in silhouette against a pure black background. Illumination provided by a sharp rim light in neon blue and violet. Sleek futuristic styling." src="https://lh3.googleusercontent.com/aida-public/AB6AXuB013OOdyT0SJ9zLCIHqaKRO-3bBoQ22rnLEVJ9k4YO3lzRh1jgZMQiQMHdKU5lxtshYQdQBzuz3rpyy1UoasC--05eD6dKUUIY7E65aUCTIVRzLJ15VypEo0uyVNvrkwzfY2aUnYvRq6tTuUme6i87MBs8T0jM0nDCe6tDfDslrGr9AAc3SJEJv2Y_P5H3bSyQP1ya23I7xtLiR3zt2VX6BA6FpfYzSy8veYCg7DzVP2A66LGIo-lNk8iaAmFdxzCCZafX2yQ2ARI"/>
</div>
</div>
</header>
<!-- Settings Content -->
<div class="p-container-padding-mobile md:p-container-padding-desktop max-w-6xl mx-auto w-full flex-1 pb-32">
<div class="mb-stack-gap">
<h1 class="font-headline-xl text-headline-xl md:text-headline-xl text-headline-lg-mobile text-on-surface">Settings</h1>
<p class="font-body-lg text-body-lg text-on-surface-variant mt-2">Manage your account preferences, integrations, and security.</p>
</div>
<!-- Profile Overview Bento -->
<section class="grid grid-cols-1 md:grid-cols-12 gap-unit mb-stack-gap">
<div class="md:col-span-8 bg-surface-container rounded-xl p-card-padding-internal border border-white/10 shadow-[0_20px_40px_rgba(0,0,0,0.3)] relative overflow-hidden flex flex-col sm:flex-row items-start sm:items-center gap-6">
<!-- Subtle Glow -->
<div class="absolute -top-24 -left-24 w-48 h-48 bg-primary-fixed-dim/10 blur-[100px] rounded-full pointer-events-none"></div>
<div class="w-24 h-24 rounded-full border border-primary-fixed-dim/30 overflow-hidden shrink-0 relative">
<img class="w-full h-full object-cover" data-alt="A high-end cinematic profile portrait of a mysterious tech professional in silhouette against a pure black background. Illumination provided by a sharp rim light in neon blue and violet. Sleek futuristic styling." src="https://lh3.googleusercontent.com/aida-public/AB6AXuByTOuR7WN2UhGE5_TB_nDyAmNJa6humtwkefD3ERmcJ7bIL4hqk89Yl9FUiDZwjt5ev7-qaWnrBhVaK7xcde2pZCrBbwgbLyfr6_tgCOUonAtdjVLYbgWtIcT7JExV5uvukHYWl2jRO7aDooJIRzj7P8LezXHZgYaZwkrdKoikp7j3h8FlveN_QDh8N3QqFIajjAiuy8D-JwGK-NSMGprzhGGLQys1bbiuLh7L6uyquU0jEVzhv7L2Lh-7UhyI3I4HkfdagYjHO2Y"/>
<button class="absolute inset-0 bg-black/50 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
<span class="material-symbols-outlined text-white">edit</span>
</button>
</div>
<div class="flex-1">
<h2 class="font-headline-lg text-headline-lg text-on-surface">Alex Mercer</h2>
<p class="font-body-md text-body-md text-on-surface-variant mb-3">alex.mercer@auracore.io</p>
<div class="flex gap-2">
<span class="bg-surface-container-highest px-3 py-1 rounded-full font-label-sm text-label-sm text-primary-fixed-dim border border-white/5">Pro Tier</span>
<span class="bg-surface-container-highest px-3 py-1 rounded-full font-label-sm text-label-sm text-secondary-fixed-dim border border-white/5">Admin</span>
</div>
</div>
<button class="mt-4 sm:mt-0 px-6 py-2 border border-primary-fixed-dim text-white rounded-lg hover:bg-primary-fixed-dim/10 transition-all font-label-md text-label-md glow-accent shrink-0">
                        Edit Profile
                    </button>
</div>
<div class="md:col-span-4 bg-surface-container-high rounded-xl p-card-padding-internal border border-white/10 shadow-[0_20px_40px_rgba(0,0,0,0.3)] flex flex-col justify-between">
<div>
<p class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Automation Usage</p>
<div class="mt-4 flex items-end gap-2">
<h3 class="font-headline-xl text-headline-xl text-primary-fixed-dim leading-none">84</h3>
<span class="font-body-md text-body-md text-on-surface-variant pb-1">/ 100k tasks</span>
</div>
</div>
<div class="w-full h-2 bg-surface-container-lowest rounded-full mt-6 overflow-hidden border border-white/5">
<div class="h-full bg-gradient-to-r from-primary-fixed-dim to-secondary-fixed-dim w-[84%] rounded-full shadow-[0_0_10px_rgba(0,218,248,0.5)]"></div>
</div>
</div>
</section>
<!-- Categorized Lists -->
<div class="grid grid-cols-1 md:grid-cols-2 gap-stack-gap">
<!-- Security -->
<div class="bg-surface-container rounded-xl border border-white/10 overflow-hidden flex flex-col shadow-[0_20px_40px_rgba(0,0,0,0.2)]">
<div class="p-6 border-b border-white/5 flex items-center gap-3">
<span class="material-symbols-outlined text-secondary-fixed-dim" style="font-variation-settings: 'FILL' 1;">security</span>
<h3 class="font-headline-md text-headline-md text-on-surface">Security</h3>
</div>
<ul class="flex flex-col flex-1 divide-y divide-white/5">
<li class="flex items-center justify-between p-6 hover:bg-white/[0.02] transition-colors cursor-pointer group">
<div>
<p class="font-body-lg text-body-lg text-on-surface">Change Password</p>
<p class="font-body-sm text-body-sm text-on-surface-variant">Last updated 3 months ago</p>
</div>
<span class="material-symbols-outlined text-on-surface-variant group-hover:text-primary-fixed-dim transition-colors">chevron_right</span>
</li>
<li class="flex items-center justify-between p-6 hover:bg-white/[0.02] transition-colors cursor-pointer group">
<div>
<p class="font-body-lg text-body-lg text-on-surface">Two-Factor Authentication</p>
<p class="font-body-sm text-body-sm text-on-surface-variant">Secure your account with 2FA</p>
</div>
<div class="bg-primary-fixed-dim text-black font-label-sm text-label-sm px-2 py-1 rounded">ENABLED</div>
</li>
<li class="flex items-center justify-between p-6 hover:bg-white/[0.02] transition-colors cursor-pointer group">
<div>
<p class="font-body-lg text-body-lg text-on-surface">Active Sessions</p>
<p class="font-body-sm text-body-sm text-on-surface-variant">Manage devices logged in</p>
</div>
<span class="material-symbols-outlined text-on-surface-variant group-hover:text-primary-fixed-dim transition-colors">chevron_right</span>
</li>
</ul>
</div>
<!-- Notifications -->
<div class="bg-surface-container rounded-xl border border-white/10 overflow-hidden flex flex-col shadow-[0_20px_40px_rgba(0,0,0,0.2)]">
<div class="p-6 border-b border-white/5 flex items-center gap-3">
<span class="material-symbols-outlined text-primary-fixed-dim" style="font-variation-settings: 'FILL' 1;">notifications_active</span>
<h3 class="font-headline-md text-headline-md text-on-surface">Notifications</h3>
</div>
<ul class="flex flex-col flex-1 divide-y divide-white/5">
<li class="flex items-center justify-between p-6 hover:bg-white/[0.02] transition-colors group">
<div>
<p class="font-body-lg text-body-lg text-on-surface">Email Alerts</p>
<p class="font-body-sm text-body-sm text-on-surface-variant">Daily summaries and critical errors</p>
</div>
<label class="relative inline-flex items-center cursor-pointer">
<input checked="" class="sr-only peer" type="checkbox" value=""/>
<div class="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-fixed-dim shadow-[inset_0_2px_4px_rgba(0,0,0,0.6)] border border-white/10"></div>
</label>
</li>
<li class="flex items-center justify-between p-6 hover:bg-white/[0.02] transition-colors group">
<div>
<p class="font-body-lg text-body-lg text-on-surface">Push Notifications</p>
<p class="font-body-sm text-body-sm text-on-surface-variant">Real-time automation triggers</p>
</div>
<label class="relative inline-flex items-center cursor-pointer">
<input class="sr-only peer" type="checkbox" value=""/>
</label></li></ul></div></div></div></main></body></html>







--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------










# Chat

<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Aura Assist - Chat</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&amp;family=JetBrains+Mono:wght@400;500;600&amp;family=Sora:wght@400;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    colors: {
                        "secondary": "#dfb7ff",
                        "on-error": "#690005",
                        "primary": "#baf2ff",
                        "tertiary-fixed": "#e2e2e2",
                        "on-tertiary-fixed": "#1b1b1b",
                        "on-tertiary-container": "#565656",
                        "outline-variant": "#3b494c",
                        "primary-fixed-dim": "#00daf8",
                        "inverse-on-surface": "#313030",
                        "error-container": "#93000a",
                        "surface-bright": "#393939",
                        "error": "#ffb4ab",
                        "surface-container-high": "#2a2a2a",
                        "inverse-primary": "#006877",
                        "surface": "#131313",
                        "inverse-surface": "#e5e2e1",
                        "primary-container": "#00e0ff",
                        "surface-container-lowest": "#0e0e0e",
                        "secondary-fixed-dim": "#dfb7ff",
                        "on-primary-fixed-variant": "#004e5a",
                        "surface-container-low": "#1c1b1b",
                        "on-error-container": "#ffdad6",
                        "surface-tint": "#00daf8",
                        "tertiary-container": "#cccccc",
                        "outline": "#859397",
                        "surface-dim": "#131313",
                        "on-secondary-fixed": "#2d004f",
                        "secondary-container": "#9d05ff",
                        "on-tertiary": "#303030",
                        "on-secondary-container": "#f7e6ff",
                        "on-primary-container": "#005f6d",
                        "on-surface": "#e5e2e1",
                        "tertiary": "#e8e8e8",
                        "secondary-fixed": "#f1daff",
                        "surface-container-highest": "#353534",
                        "on-surface-variant": "#bac9cd",
                        "surface-variant": "#353534",
                        "tertiary-fixed-dim": "#c6c6c6",
                        "on-tertiary-fixed-variant": "#474747",
                        "surface-container": "#201f1f",
                        "on-secondary": "#4b007e",
                        "on-primary": "#00363f",
                        "on-secondary-fixed-variant": "#6b00b0",
                        "on-background": "#e5e2e1",
                        "primary-fixed": "#a5eeff",
                        "background": "#131313",
                        "on-primary-fixed": "#001f25"
                    },
                    borderRadius: {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    spacing: {
                        "container-padding-desktop": "64px",
                        "card-padding-internal": "32px",
                        "gutter-desktop": "32px",
                        "gutter-mobile": "16px",
                        "container-padding-mobile": "24px",
                        "unit": "8px",
                        "stack-gap": "24px"
                    },
                    fontFamily: {
                        "headline-md": ["Sora"],
                        "label-sm": ["JetBrains Mono"],
                        "body-lg": ["Geist"],
                        "headline-lg-mobile": ["Sora"],
                        "body-md": ["Geist"],
                        "label-md": ["JetBrains Mono"],
                        "body-sm": ["Geist"],
                        "headline-xl": ["Sora"],
                        "headline-lg": ["Sora"]
                    },
                    fontSize: {
                        "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
                        "label-sm": ["10px", { lineHeight: "14px", letterSpacing: "0.08em", fontWeight: "600" }],
                        "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }],
                        "headline-lg-mobile": ["28px", { lineHeight: "36px", fontWeight: "600" }],
                        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
                        "label-md": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "500" }],
                        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
                        "headline-xl": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "700" }],
                        "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "600" }]
                    }
                }
            }
        }
    </script>
<style>
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
        .glow-effect { box-shadow: 0 0 15px rgba(0, 218, 248, 0.2); }
    </style>
</head>
<body class="bg-background text-on-background font-body-md text-body-md overflow-hidden selection:bg-primary-container selection:text-on-primary-container min-h-screen flex">
<!-- SideNavBar -->
<nav class="fixed left-0 top-0 h-full flex flex-col py-8 z-40 bg-surface-container-lowest dark:bg-surface-container-lowest w-64 border-r border-white/10 shadow-2xl shadow-black">
<div class="px-6 mb-8 flex items-center gap-4">
<div class="w-10 h-10 rounded-full border border-white/20 overflow-hidden bg-surface-variant flex items-center justify-center">
<img alt="Assistant Avatar" class="w-full h-full object-cover" data-alt="A futuristic AI avatar representing Aura Core, featuring a glowing holographic eye interface set against a pure black background. Deep cinematic lighting highlights the subtle metallic sheen and energetic neon blue data streams floating around the core. Extremely detailed and moody." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAjMzttUcMYIKIwWnl-XMQS5VM0-3K6PJ285IV8byR1nlgit2Dvha-5iGil6AN47JYYxJ7D2n95jzJvL8FO82A8wi4ecTlNE_sBeGqZf3cL0bHHvdNMsPIQTnVe_zDIakCHyvmmn-veWVjguJ-XEaQ2ahznPQlBfFH0-RRLvKHEBEIWpTGbfkV9Rhwa6FUxzmEj3nKl4bDzWHueK2XizdIotDika72oMuT2fSUiHORiIZPpn2UNanYGWh4VdyHX-esDFONug4CfUOE"/>
</div>
<div>
<h1 class="text-headline-lg font-headline-lg text-primary-fixed-dim text-lg leading-tight">Aura Core</h1>
<span class="text-label-sm font-label-sm text-secondary-fixed-dim flex items-center gap-1 mt-1"><span class="w-2 h-2 rounded-full bg-primary-fixed-dim animate-pulse"></span> Automation Active</span>
</div>
</div>
<div class="px-6 mb-8">
<button class="w-full py-3 px-4 rounded-xl border border-primary-fixed-dim text-primary-fixed-dim font-label-md text-label-md flex items-center justify-center gap-2 hover:bg-primary-fixed-dim/10 transition-all glow-effect">
<span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 0;">add</span>
                New Task
            </button>
</div>
<div class="flex flex-col gap-2 flex-grow">
<!-- Dashboard (Inactive) -->
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined">dashboard</span>
<span class="text-label-md font-label-md">Dashboard</span>
</a>
<!-- Automations (Inactive) -->
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined">bolt</span>
<span class="text-label-md font-label-md">Automations</span>
</a>
<!-- Chat (Active) -->
<a class="text-primary-fixed-dim font-bold border-r-2 border-primary-fixed-dim pr-4 flex items-center gap-3 px-4 py-3 bg-white/5" href="#">
<span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">chat_bubble</span>
<span class="text-label-md font-label-md">Chat</span>
</a>
<!-- Calendar (Inactive) -->
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined">calendar_today</span>
<span class="text-label-md font-label-md">Calendar</span>
</a>
<!-- Analytics (Inactive) -->
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined">analytics</span>
<span class="text-label-md font-label-md">Analytics</span>
</a>
</div>
<div class="mt-auto flex flex-col gap-2">
<!-- Help -->
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined">help</span>
<span class="text-label-md font-label-md">Help</span>
</a>
<!-- Sign Out -->
<a class="text-on-surface-variant flex items-center gap-3 px-4 py-3 hover:bg-white/5 hover:text-secondary-fixed-dim transition-all hover:translate-x-1 duration-200" href="#">
<span class="material-symbols-outlined">logout</span>
<span class="text-label-md font-label-md">Sign Out</span>
</a>
</div>
</nav>
<!-- Main Content Area -->
<main class="ml-64 flex-grow flex h-screen overflow-hidden">
<!-- Recent Sessions Sub-Sidebar -->
<aside class="w-72 bg-surface-container-low border-r border-white/10 flex flex-col hidden lg:flex relative z-10">
<div class="p-6 border-b border-white/5">
<h2 class="text-headline-md font-headline-md text-lg text-on-surface">Conversations</h2>
<div class="mt-4 relative">
<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">search</span>
<input class="w-full bg-surface text-on-surface text-body-sm font-body-sm rounded-lg pl-9 pr-4 py-2 border border-white/10 focus:border-primary-fixed-dim focus:ring-0 focus:outline-none placeholder:text-on-surface-variant/50 transition-colors" placeholder="Search sessions..." type="text"/>
</div>
</div>
<div class="flex-grow overflow-y-auto custom-scrollbar p-4 flex flex-col gap-2">
<!-- Session Item (Active) -->
<button class="w-full text-left p-3 rounded-lg bg-surface-container-highest border border-primary-fixed-dim/30 shadow-[0_4px_12px_rgba(0,0,0,0.5)] transition-all">
<div class="flex justify-between items-center mb-1">
<span class="text-label-md font-label-md text-primary-fixed-dim">System Optimization</span>
<span class="text-label-sm font-label-sm text-on-surface-variant">Just now</span>
</div>
<p class="text-body-sm font-body-sm text-on-surface-variant truncate">I have analyzed the current network latency...</p>
</button>
<!-- Session Item -->
<button class="w-full text-left p-3 rounded-lg border border-white/5 hover:bg-white/5 hover:border-white/10 transition-all group">
<div class="flex justify-between items-center mb-1">
<span class="text-label-md font-label-md text-on-surface group-hover:text-secondary-fixed-dim transition-colors">Data Processing Pipeline</span>
<span class="text-label-sm font-label-sm text-on-surface-variant">2h ago</span>
</div>
<p class="text-body-sm font-body-sm text-on-surface-variant truncate">The batch job completed with 3 warnings.</p>
</button>
<!-- Session Item -->
<button class="w-full text-left p-3 rounded-lg border border-white/5 hover:bg-white/5 hover:border-white/10 transition-all group">
<div class="flex justify-between items-center mb-1">
<span class="text-label-md font-label-md text-on-surface group-hover:text-secondary-fixed-dim transition-colors">Security Audit Report</span>
<span class="text-label-sm font-label-sm text-on-surface-variant">Yesterday</span>
</div>
<p class="text-body-sm font-body-sm text-on-surface-variant truncate">Generating the weekly vulnerability summary.</p>
</button>
<!-- Session Item -->
<button class="w-full text-left p-3 rounded-lg border border-white/5 hover:bg-white/5 hover:border-white/10 transition-all group">
<div class="flex justify-between items-center mb-1">
<span class="text-label-md font-label-md text-on-surface group-hover:text-secondary-fixed-dim transition-colors">UI Design Ideation</span>
<span class="text-label-sm font-label-sm text-on-surface-variant">Oct 24</span>
</div>
<p class="text-body-sm font-body-sm text-on-surface-variant truncate">Drafting new components for the dashboard.</p>
</button>
</div>
</aside>
<!-- Chat Interface -->
<section class="flex-grow flex flex-col bg-surface relative">
<!-- Optional subtle background gradient -->
<div class="absolute inset-0 bg-gradient-to-b from-primary-fixed-dim/5 to-transparent pointer-events-none"></div>
<!-- Chat Header -->
<header class="h-16 border-b border-white/10 flex items-center justify-between px-6 bg-surface/80 backdrop-blur-md z-10">
<div class="flex items-center gap-3">
<h2 class="text-headline-md font-headline-md text-xl text-on-surface">System Optimization</h2>
<span class="bg-surface-container-high px-2 py-1 rounded text-label-sm font-label-sm text-primary-fixed-dim border border-white/10">Active Session</span>
</div>
<div class="flex items-center gap-2">
<button class="p-2 rounded-lg text-on-surface-variant hover:text-primary-fixed-dim hover:bg-white/5 transition-colors">
<span class="material-symbols-outlined text-xl">ios_share</span>
</button>
<button class="p-2 rounded-lg text-on-surface-variant hover:text-primary-fixed-dim hover:bg-white/5 transition-colors">
<span class="material-symbols-outlined text-xl">more_vert</span>
</button>
</div>
</header>
<!-- Chat Messages Area -->
<div class="flex-grow overflow-y-auto custom-scrollbar p-container-padding-mobile md:p-gutter-desktop flex flex-col gap-stack-gap z-10 relative">
<!-- System Message Date -->
<div class="text-center">
<span class="text-label-sm font-label-sm text-on-surface-variant bg-surface-container px-3 py-1 rounded-full border border-white/5">Today, 10:42 AM</span>
</div>
<!-- User Message -->
<div class="flex gap-4 justify-end">
<div class="max-w-[75%] md:max-w-[60%] flex flex-col items-end">
<div class="flex items-center gap-2 mb-1">
<span class="text-label-md font-label-md text-secondary-fixed-dim">You</span>
</div>
<div class="bg-surface-container-high border border-white/10 p-5 rounded-2xl rounded-tr-sm shadow-[0_10px_20px_rgba(0,0,0,0.4)] text-on-surface">
<p class="text-body-md font-body-md">Can you run a diagnostic on the main database cluster? The latency has been spiking over the last 15 minutes.</p>
</div>
</div>
<div class="w-8 h-8 rounded-full bg-secondary-fixed-dim/20 border border-secondary-fixed-dim flex items-center justify-center flex-shrink-0 mt-6 shadow-[0_0_10px_rgba(223,183,255,0.2)]">
<span class="material-symbols-outlined text-secondary-fixed-dim text-sm">person</span>
</div>
</div>
<!-- AI Message -->
<div class="flex gap-4">
<div class="w-8 h-8 rounded-full bg-primary-fixed-dim/20 border border-primary-fixed-dim flex items-center justify-center flex-shrink-0 mt-6 shadow-[0_0_10px_rgba(0,218,248,0.2)] relative">
<span class="material-symbols-outlined text-primary-fixed-dim text-sm" style="font-variation-settings: 'FILL' 1;">smart_toy</span>
<span class="absolute -bottom-1 -right-1 w-3 h-3 bg-primary-fixed-dim rounded-full border border-surface animate-pulse"></span>
</div>
<div class="max-w-[75%] md:max-w-[60%] flex flex-col items-start">
<div class="flex items-center gap-2 mb-1">
<span class="text-label-md font-label-md text-primary-fixed-dim">Aura Core</span>
</div>
<div class="bg-surface-container border border-primary-fixed-dim/20 p-5 rounded-2xl rounded-tl-sm shadow-[0_20px_40px_rgba(0,0,0,0.6)] text-on-surface relative overflow-hidden group">
<!-- Subtle glow background on AI message -->
<div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary-fixed-dim to-secondary-fixed-dim opacity-50"></div>
<p class="text-body-md font-body-md mb-4 text-on-background">Initiating diagnostic scan on cluster <code class="bg-surface-container-lowest border border-white/10 px-1 py-0.5 rounded text-secondary-fixed-dim font-label-sm text-sm">DB-PRD-01</code>...</p>
<div class="bg-surface-container-lowest border border-white/10 rounded-lg p-4 mb-4">
<div class="flex justify-between items-center mb-2">
<span class="text-label-sm font-label-sm text-on-surface-variant">Scan Progress</span>
<span class="text-label-sm font-label-sm text-primary-fixed-dim">100%</span>
</div>
<div class="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
<div class="bg-gradient-to-r from-primary-fixed-dim to-secondary-fixed-dim w-full h-full shadow-[0_0_8px_rgba(0,218,248,0.8)]"></div>
</div>
</div>
<p class="text-body-md font-body-md text-on-background mb-3">Scan complete. I detected a bottleneck in the indexing queue. Several complex queries from the analytics service are locking rows.</p>
<div class="flex gap-2 mt-4">
<button class="px-3 py-1.5 rounded border border-white/10 bg-surface-container-high text-label-md font-label-md text-on-surface hover:border-primary-fixed-dim transition-colors flex items-center gap-1">
<span class="material-symbols-outlined text-sm">terminal</span>
                                    View Logs
                                </button>
<button class="px-3 py-1.5 rounded border border-primary-fixed-dim bg-primary-fixed-dim/10 text-label-md font-label-md text-primary-fixed-dim hover:bg-primary-fixed-dim/20 transition-colors flex items-center gap-1 shadow-[0_0_10px_rgba(0,218,248,0.1)]">
<span class="material-symbols-outlined text-sm">stop_circle</span>
                                    Kill Queries
                                </button>
</div>
</div>
</div>
</div>
<!-- User Message -->
<div class="flex gap-4 justify-end">
<div class="max-w-[75%] md:max-w-[60%] flex flex-col items-end">
<div class="flex items-center gap-2 mb-1">
<span class="text-label-md font-label-md text-secondary-fixed-dim">You</span>
</div>
<div class="bg-surface-container-high border border-white/10 p-5 rounded-2xl rounded-tr-sm shadow-[0_10px_20px_rgba(0,0,0,0.4)] text-on-surface">
<p class="text-body-md font-body-md">Kill the queries and restart the indexing service.</p>
</div>
</div>
<div class="w-8 h-8 rounded-full bg-secondary-fixed-dim/20 border border-secondary-fixed-dim flex items-center justify-center flex-shrink-0 mt-6 shadow-[0_0_10px_rgba(223,183,255,0.2)]">
<span class="material-symbols-outlined text-secondary-fixed-dim text-sm">person</span>
</div>
</div>
<!-- AI Typing Indicator -->
<div class="flex gap-4">
<div class="w-8 h-8 rounded-full bg-primary-fixed-dim/20 border border-primary-fixed-dim flex items-center justify-center flex-shrink-0 mt-2 shadow-[0_0_10px_rgba(0,218,248,0.2)]">
<span class="material-symbols-outlined text-primary-fixed-dim text-sm" style="font-variation-settings: 'FILL' 1;">smart_toy</span>
</div>
<div class="bg-surface-container border border-white/10 px-5 py-4 rounded-2xl rounded-tl-sm w-fit flex items-center gap-2">
<div class="w-1.5 h-1.5 rounded-full bg-primary-fixed-dim animate-bounce" style="animation-delay: 0ms;"></div>
<div class="w-1.5 h-1.5 rounded-full bg-primary-fixed-dim animate-bounce" style="animation-delay: 150ms;"></div>
<div class="w-1.5 h-1.5 rounded-full bg-primary-fixed-dim animate-bounce" style="animation-delay: 300ms;"></div>
</div>
</div>
</div>
<!-- Input Area -->
<div class="p-4 md:p-6 bg-surface-container-low border-t border-white/5 relative z-10">
<div class="max-w-4xl mx-auto relative group">
<!-- Subtle glow behind input -->
<div class="absolute -inset-0.5 bg-gradient-to-r from-primary-fixed-dim/20 to-secondary-fixed-dim/20 rounded-xl blur opacity-30 group-hover:opacity-60 transition duration-500"></div>
<div class="relative bg-surface border border-white/10 rounded-xl flex items-end p-2 shadow-[0_20px_40px_rgba(0,0,0,0.8)] focus-within:border-primary-fixed-dim/50 transition-colors">
<button class="p-3 text-on-surface-variant hover:text-secondary-fixed-dim transition-colors rounded-lg flex-shrink-0 mb-0.5">
<span class="material-symbols-outlined">attach_file</span>
</button>
<textarea class="w-full bg-transparent text-on-surface font-body-md text-body-md border-none focus:ring-0 resize-none py-3 px-2 max-h-32 min-h-[44px] custom-scrollbar placeholder:text-on-surface-variant/40" oninput="this.style.height = ''; this.style.height = Math.min(this.scrollHeight, 128) + 'px'" placeholder="Type a message or command..." rows="1"></textarea>
<button class="p-3 bg-gradient-to-br from-primary-fixed-dim to-secondary-fixed-dim text-background rounded-lg flex-shrink-0 shadow-[0_0_15px_rgba(0,218,248,0.3)] hover:shadow-[0_0_25px_rgba(0,218,248,0.5)] transition-all hover:scale-105 active:scale-95 mb-0.5 ml-2">
<span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">send</span>
</button>
</div>
</div>
<div class="text-center mt-3">
<span class="text-label-sm font-label-sm text-on-surface-variant/50">Aura Core can make mistakes. Verify critical system actions.</span>
</div>
</div>
</section>
</main>
</body></html>

