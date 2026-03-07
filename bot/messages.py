"""
bot/messages.py
==============
Multi-language message templates for UGC Video Pro Telegram Bot.
Supported languages: zh (Chinese), en (English), it (Italian)

Usage:
    from bot.messages import get_message, MESSAGES
    text = get_message("welcome", lang="zh")
    text = get_message("generating", lang="en", model="Sora 2", duration=30, segment=1, total=4)
"""

from typing import Any

# ─────────────────────────────────────────────────────────────
# Full message catalog per language
# ─────────────────────────────────────────────────────────────

MESSAGES: dict[str, dict[str, str]] = {

    # ── Chinese (Simplified) ─────────────────────────────────
    "zh": {
        # Onboarding
        "welcome": (
            "🎬 *UGC视频生成器* 欢迎使用！\n\n"
            "我可以根据您的产品图片或文字描述，使用最先进的AI模型生成高质量UGC产品视频。\n\n"
            "请先选择生成模式："
        ),
        "help": (
            "📖 *帮助说明*\n\n"
            "*三种模式：*\n"
            "• 🖼 `图片转视频` — 上传产品图，AI生成展示视频\n"
            "• ✍️ `文字转视频` — 描述产品，AI凭文字生成视频\n"
            "• 🔗 `URL参考转视频` — 提供商品链接+产品图，AI提取内容生成视频\n\n"
            "*支持的时长：* 15 / 25 / 30 / 60 / 120 秒\n\n"
            "*支持的AI模型：*\n"
            "• Sora 2 / Sora 2 Pro（OpenAI）\n"
            "• Seedance 2.0（强大的参考锁定）\n"
            "• Veo 3.0 / 3.0 Pro / 3.1 Pro（Google，最佳帧链）\n\n"
            "发送 /start 开始生成"
        ),

        # Mode selection
        "select_mode": "请选择生成模式：",
        "mode_text_to_video": "✍️ 文字转视频",
        "mode_image_to_video": "🖼 图片转视频",
        "mode_url_to_video": "🔗 URL参考转视频",

        # Model selection
        "select_model": "🤖 请选择AI模型：\n\n_(括号内为单片段最大时长)_",
        "model_sora_2": "⚡ Sora 2（最长12秒/片）",
        "model_sora_2_pro": "🚀 Sora 2 Pro（最长25秒/片）",
        "model_seedance_2": "🔒 Seedance 2.0（最长10秒/片）",
        "model_veo_3": "🎬 Veo 3.0（最长8秒/片）",
        "model_veo_3_pro": "⭐ Veo 3.0 Pro（最长8秒/片）",
        "model_veo_31_pro": "💎 Veo 3.1 Pro（最长8秒/片，推荐）",

        # Duration selection (dynamic multiples)
        "select_duration": "⏱ 请选择视频时长：\n\n_当前模型单次最长 {max_clip}秒，时长必须为 {max_clip} 的倍数_",
        "duration_15": "15秒（快速）",
        "duration_25": "25秒",
        "duration_30": "30秒（推荐）",
        "duration_60": "60秒（1分钟）",
        "duration_120": "120秒（2分钟）",
        "duration_n_sec": "{n}秒",
        "duration_custom": "✏️ 自定义时长",
        "duration_custom_prompt": "请输入自定义视频时长（秒）：\n\n_必须为 {max_clip} 的整数倍（如 {examples}）_",
        "duration_invalid_hint": "⚠️ {value}秒 不是 {max_clip} 的整数倍。\n\n最接近的有效时长: *{nearest}秒*\n\n请重新输入或点击下方按钮选择：",
        "duration_use_nearest": "使用 {nearest}秒",

        # Product description prompt (after image upload)
        "ask_add_description": "📝 是否需要添加产品说明文字？\n\n_产品说明将辅助AI更准确地分析产品特性和生成视频脚本_",
        "btn_yes_add_desc": "✅ 添加说明",
        "btn_no_skip_desc": "⏭ 跳过，直接生成",
        "send_product_description": "请输入产品说明文字：\n\n_例如：材质、功能、卖点、适用场景等_",

        # Language selection
        "select_language": "🌍 选择视频旁白语言：",
        "lang_zh": "🇨🇳 中文",
        "lang_en": "🇬🇧 English",
        "lang_it": "🇮🇹 Italiano",

        # Content input prompts
        "send_text": (
            "✍️ 请发送产品描述文字。\n\n"
            "示例：\n"
            "_一款无线降噪耳机，银色金属外壳，旋转折叠设计，适合商务出行_"
        ),
        "send_image": (
            "🖼 请发送产品图片。\n\n"
            "• 支持JPG、PNG格式\n"
            "• 建议使用白底或纯色背景\n"
            "• 图片越清晰，生成效果越好"
        ),
        "send_url_and_image": (
            "🔗 请先发送商品链接（URL），然后发送产品图片。\n\n"
            "示例链接：\n"
            "`https://www.amazon.com/dp/B09XXXXX`\n\n"
            "⚠️ 请先发URL，图片稍后上传"
        ),
        "send_image_after_url": (
            "✅ 链接已收到！\n现在请发送产品图片："
        ),
        "url_received": "🔗 链接已接收：`{url}`",

        # Processing messages
        "analyzing_image": "🔍 正在分析产品图片...",
        "extracting_url": "🌐 正在提取链接内容...",
        "generating_script": "📝 正在生成视频脚本（{segments}个场景）...",
        "generating": (
            "⏳ 正在生成视频片段 {segment}/{total}...\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📌 模型: `{model}`\n"
            "⏱ 总时长: `{duration}` 秒\n"
            "🎬 当前场景: `{segment_prompt}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "_预计等待: {eta}_"
        ),
        "polling": "⏳ 正在等待 {model} 渲染完成... ({attempt}/{max_retries})",
        "stitching": "🎞 正在拼接 {count} 个视频片段...",
        "uploading_drive": "📤 正在上传到Google Drive...",

        # Completion messages
        "complete": (
            "✅ *视频生成完成！*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎬 模型: `{model}`\n"
            "⏱ 总时长: `{duration}` 秒\n"
            "🎞 片段数: `{segments}` 个\n"
            "⏰ 耗时: `{elapsed}`\n"
            "📂 文件: `{filename}`"
        ),
        "drive_complete": "☁️ 已保存到Google Drive\n📎 [点击查看]({link})",
        "no_drive": "💾 视频已直接发送（未配置Google Drive）",

        # Error messages
        "error": "❌ 生成失败\n\n原因: `{error}`\n\n请重试或更换模型。",
        "error_model_timeout": "⏰ 模型响应超时，请稍后重试。",
        "error_api": "🔌 API错误: `{error}`",
        "error_no_permission": "🚫 您没有权限使用此Bot。",
        "error_invalid_url": "❌ 无效的URL，请发送有效的商品链接。",
        "error_image_too_large": "❌ 图片过大（最大20MB），请压缩后重试。",
        "error_ffmpeg": "❌ 视频处理失败: `{error}`",
        "error_drive_upload": "⚠️ Google Drive上传失败，视频将直接发送。",

        # Cancellation
        "cancel": "已取消当前操作。发送 /start 重新开始。",
        "confirm_cancel": "确认取消当前视频生成？",
        "btn_confirm": "✅ 确认取消",
        "btn_back": "↩️ 返回",

        # Summary shown before generation starts
        "generation_summary": (
            "📋 *生成配置确认*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎭 模式: `{mode}`\n"
            "🤖 模型: `{model}`\n"
            "⏱ 时长: `{duration}` 秒\n"
            "🎞 片段数: `{segments}` 个\n"
            "🌍 语言: `{language}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "确认开始生成？"
        ),
        "btn_generate": "🎬 开始生成",
        "btn_cancel": "❌ 取消",

        # Misc
        "unknown_command": "未知命令，发送 /start 开始",
        "busy": "⚙️ 正在处理您的上一个请求，请稍候...",
        "frame_chaining_notice": "🔗 帧链技术已启用，确保场景之间流畅衔接",
    },

    # ── English ──────────────────────────────────────────────
    "en": {
        # Onboarding
        "welcome": (
            "🎬 *UGC Video Generator* — Welcome!\n\n"
            "I generate high-quality UGC product videos using state-of-the-art AI models.\n"
            "Upload a product photo or describe your product to get started.\n\n"
            "Please choose a generation mode:"
        ),
        "help": (
            "📖 *Help*\n\n"
            "*Three modes:*\n"
            "• 🖼 `Image to Video` — Upload a product photo, AI creates a showcase video\n"
            "• ✍️ `Text to Video` — Describe the product, AI generates video from text\n"
            "• 🔗 `URL to Video` — Provide a product URL + photo, AI extracts content\n\n"
            "*Supported durations:* 15 / 25 / 30 / 60 / 120 seconds\n\n"
            "*Supported AI models:*\n"
            "• Sora 2 / Sora 2 Pro (OpenAI)\n"
            "• Seedance 2.0 (strong reference locking)\n"
            "• Veo 3.0 / 3.0 Pro / 3.1 Pro (Google, best frame chaining)\n\n"
            "Send /start to begin"
        ),

        # Mode selection
        "select_mode": "Choose a generation mode:",
        "mode_text_to_video": "✍️ Text to Video",
        "mode_image_to_video": "🖼 Image to Video",
        "mode_url_to_video": "🔗 URL Reference to Video",

        # Model selection
        "select_model": "🤖 Select an AI model:\n\n_(brackets show max clip duration)_",
        "model_sora_2": "⚡ Sora 2 (up to 12s/clip)",
        "model_sora_2_pro": "🚀 Sora 2 Pro (up to 25s/clip)",
        "model_seedance_2": "🔒 Seedance 2.0 (up to 10s/clip)",
        "model_veo_3": "🎬 Veo 3.0 (up to 8s/clip)",
        "model_veo_3_pro": "⭐ Veo 3.0 Pro (up to 8s/clip)",
        "model_veo_31_pro": "💎 Veo 3.1 Pro (up to 8s/clip, recommended)",

        # Duration selection (dynamic multiples)
        "select_duration": "⏱ Select video duration:\n\n_Current model max clip: {max_clip}s. Duration must be a multiple of {max_clip}_",
        "duration_15": "15 seconds (quick)",
        "duration_25": "25 seconds",
        "duration_30": "30 seconds (recommended)",
        "duration_60": "60 seconds (1 minute)",
        "duration_120": "120 seconds (2 minutes)",
        "duration_n_sec": "{n} seconds",
        "duration_custom": "✏️ Custom duration",
        "duration_custom_prompt": "Enter a custom video duration (seconds):\n\n_Must be a multiple of {max_clip} (e.g. {examples})_",
        "duration_invalid_hint": "⚠️ {value}s is not a multiple of {max_clip}.\n\nNearest valid duration: *{nearest}s*\n\nPlease re-enter or select below:",
        "duration_use_nearest": "Use {nearest}s",

        # Product description prompt (after image upload)
        "ask_add_description": "📝 Would you like to add a product description?\n\n_A description helps the AI analyze product features and generate a better script_",
        "btn_yes_add_desc": "✅ Add description",
        "btn_no_skip_desc": "⏭ Skip, generate now",
        "send_product_description": "Please enter a product description:\n\n_e.g. material, features, selling points, use cases_",

        # Language selection
        "select_language": "🌍 Select narration language:",
        "lang_zh": "🇨🇳 Chinese",
        "lang_en": "🇬🇧 English",
        "lang_it": "🇮🇹 Italian",

        # Content input prompts
        "send_text": (
            "✍️ Please send a product description.\n\n"
            "Example:\n"
            "_A wireless noise-canceling headphone with silver metal shell, "
            "folding design, ideal for business travel_"
        ),
        "send_image": (
            "🖼 Please send a product photo.\n\n"
            "• JPG or PNG format\n"
            "• White or plain background recommended\n"
            "• Higher resolution = better results"
        ),
        "send_url_and_image": (
            "🔗 First send the product URL, then the product photo.\n\n"
            "Example:\n"
            "`https://www.amazon.com/dp/B09XXXXX`\n\n"
            "⚠️ Send the URL first, then the image"
        ),
        "send_image_after_url": (
            "✅ URL received!\nNow please send the product photo:"
        ),
        "url_received": "🔗 URL received: `{url}`",

        # Processing messages
        "analyzing_image": "🔍 Analyzing product image...",
        "extracting_url": "🌐 Extracting content from URL...",
        "generating_script": "📝 Generating video script ({segments} scenes)...",
        "generating": (
            "⏳ Generating video clip {segment}/{total}...\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📌 Model: `{model}`\n"
            "⏱ Total duration: `{duration}` seconds\n"
            "🎬 Current scene: `{segment_prompt}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "_Estimated wait: {eta}_"
        ),
        "polling": "⏳ Waiting for {model} to render... ({attempt}/{max_retries})",
        "stitching": "🎞 Stitching {count} video clips together...",
        "uploading_drive": "📤 Uploading to Google Drive...",

        # Completion
        "complete": (
            "✅ *Video generation complete!*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎬 Model: `{model}`\n"
            "⏱ Duration: `{duration}` seconds\n"
            "🎞 Clips: `{segments}`\n"
            "⏰ Elapsed: `{elapsed}`\n"
            "📂 File: `{filename}`"
        ),
        "drive_complete": "☁️ Saved to Google Drive\n📎 [Open link]({link})",
        "no_drive": "💾 Video sent directly (Google Drive not configured)",

        # Errors
        "error": "❌ Generation failed\n\nReason: `{error}`\n\nPlease retry or change model.",
        "error_model_timeout": "⏰ Model timed out, please retry later.",
        "error_api": "🔌 API error: `{error}`",
        "error_no_permission": "🚫 You do not have permission to use this bot.",
        "error_invalid_url": "❌ Invalid URL. Please send a valid product link.",
        "error_image_too_large": "❌ Image too large (max 20MB). Please compress and retry.",
        "error_ffmpeg": "❌ Video processing failed: `{error}`",
        "error_drive_upload": "⚠️ Google Drive upload failed, sending video directly.",

        # Cancellation
        "cancel": "Operation cancelled. Send /start to begin again.",
        "confirm_cancel": "Confirm cancellation of current video generation?",
        "btn_confirm": "✅ Yes, cancel",
        "btn_back": "↩️ Go back",

        # Summary
        "generation_summary": (
            "📋 *Generation Summary*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎭 Mode: `{mode}`\n"
            "🤖 Model: `{model}`\n"
            "⏱ Duration: `{duration}` seconds\n"
            "🎞 Clips: `{segments}`\n"
            "🌍 Language: `{language}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Confirm and start generation?"
        ),
        "btn_generate": "🎬 Generate Video",
        "btn_cancel": "❌ Cancel",

        # Misc
        "unknown_command": "Unknown command. Send /start to begin.",
        "busy": "⚙️ Processing your previous request, please wait...",
        "frame_chaining_notice": "🔗 Frame chaining enabled for seamless scene transitions",
    },

    # ── Italian ──────────────────────────────────────────────
    "it": {
        # Onboarding
        "welcome": (
            "🎬 *Generatore Video UGC* — Benvenuto!\n\n"
            "Genero video di prodotto UGC di alta qualità usando modelli AI avanzati.\n"
            "Carica una foto del prodotto o descrivilo per iniziare.\n\n"
            "Scegli una modalità:"
        ),
        "help": (
            "📖 *Aiuto*\n\n"
            "*Tre modalità:*\n"
            "• 🖼 `Immagine a Video` — Carica una foto, l'AI crea un video showcase\n"
            "• ✍️ `Testo a Video` — Descrivi il prodotto, l'AI genera il video\n"
            "• 🔗 `URL a Video` — Fornisci link prodotto + foto, l'AI estrae i dati\n\n"
            "*Durate supportate:* 15 / 25 / 30 / 60 / 120 secondi\n\n"
            "*Modelli AI supportati:*\n"
            "• Sora 2 / Sora 2 Pro (OpenAI)\n"
            "• Seedance 2.0 (blocco riferimento avanzato)\n"
            "• Veo 3.0 / 3.0 Pro / 3.1 Pro (Google, miglior frame chaining)\n\n"
            "Invia /start per iniziare"
        ),

        # Mode selection
        "select_mode": "Scegli la modalità di generazione:",
        "mode_text_to_video": "✍️ Testo a Video",
        "mode_image_to_video": "🖼 Immagine a Video",
        "mode_url_to_video": "🔗 URL a Video",

        # Model selection
        "select_model": "🤖 Seleziona il modello AI:\n\n_(tra parentesi la durata massima per clip)_",
        "model_sora_2": "⚡ Sora 2 (fino a 12s/clip)",
        "model_sora_2_pro": "🚀 Sora 2 Pro (fino a 25s/clip)",
        "model_seedance_2": "🔒 Seedance 2.0 (fino a 10s/clip)",
        "model_veo_3": "🎬 Veo 3.0 (fino a 8s/clip)",
        "model_veo_3_pro": "⭐ Veo 3.0 Pro (fino a 8s/clip)",
        "model_veo_31_pro": "💎 Veo 3.1 Pro (fino a 8s/clip, consigliato)",

        # Duration selection (dynamic multiples)
        "select_duration": "⏱ Seleziona la durata del video:\n\n_Durata max per clip del modello: {max_clip}s. La durata deve essere un multiplo di {max_clip}_",
        "duration_15": "15 secondi (veloce)",
        "duration_25": "25 secondi",
        "duration_30": "30 secondi (consigliato)",
        "duration_60": "60 secondi (1 minuto)",
        "duration_120": "120 secondi (2 minuti)",
        "duration_n_sec": "{n} secondi",
        "duration_custom": "✏️ Durata personalizzata",
        "duration_custom_prompt": "Inserisci la durata personalizzata (secondi):\n\n_Deve essere un multiplo di {max_clip} (es. {examples})_",
        "duration_invalid_hint": "⚠️ {value}s non è un multiplo di {max_clip}.\n\nDurata valida più vicina: *{nearest}s*\n\nReinserisci o seleziona sotto:",
        "duration_use_nearest": "Usa {nearest}s",

        # Product description prompt (after image upload)
        "ask_add_description": "📝 Vuoi aggiungere una descrizione del prodotto?\n\n_La descrizione aiuta l'AI ad analizzare meglio il prodotto e generare uno script migliore_",
        "btn_yes_add_desc": "✅ Aggiungi descrizione",
        "btn_no_skip_desc": "⏭ Salta, genera ora",
        "send_product_description": "Inserisci la descrizione del prodotto:\n\n_es. materiali, funzionalità, punti di forza, scenari d'uso_",

        # Language selection
        "select_language": "🌍 Scegli la lingua della narrazione:",
        "lang_zh": "🇨🇳 Cinese",
        "lang_en": "🇬🇧 Inglese",
        "lang_it": "🇮🇹 Italiano",

        # Content input prompts
        "send_text": (
            "✍️ Invia una descrizione del prodotto.\n\n"
            "Esempio:\n"
            "_Cuffie wireless con cancellazione del rumore, scocca in metallo argentato, "
            "design pieghevole, ideali per viaggi di lavoro_"
        ),
        "send_image": (
            "🖼 Invia una foto del prodotto.\n\n"
            "• Formato JPG o PNG\n"
            "• Sfondo bianco o neutro consigliato\n"
            "• Maggiore risoluzione = risultati migliori"
        ),
        "send_url_and_image": (
            "🔗 Prima invia l'URL del prodotto, poi la foto.\n\n"
            "Esempio:\n"
            "`https://www.amazon.it/dp/B09XXXXX`\n\n"
            "⚠️ Prima l'URL, poi l'immagine"
        ),
        "send_image_after_url": (
            "✅ URL ricevuto!\nOra invia la foto del prodotto:"
        ),
        "url_received": "🔗 URL ricevuto: `{url}`",

        # Processing messages
        "analyzing_image": "🔍 Analisi immagine prodotto in corso...",
        "extracting_url": "🌐 Estrazione contenuto dall'URL in corso...",
        "generating_script": "📝 Generazione script video ({segments} scene)...",
        "generating": (
            "⏳ Generazione clip video {segment}/{total}...\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📌 Modello: `{model}`\n"
            "⏱ Durata totale: `{duration}` secondi\n"
            "🎬 Scena corrente: `{segment_prompt}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "_Attesa stimata: {eta}_"
        ),
        "polling": "⏳ In attesa del rendering di {model}... ({attempt}/{max_retries})",
        "stitching": "🎞 Unione di {count} clip video in corso...",
        "uploading_drive": "📤 Caricamento su Google Drive...",

        # Completion
        "complete": (
            "✅ *Video generato con successo!*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎬 Modello: `{model}`\n"
            "⏱ Durata: `{duration}` secondi\n"
            "🎞 Clip: `{segments}`\n"
            "⏰ Tempo: `{elapsed}`\n"
            "📂 File: `{filename}`"
        ),
        "drive_complete": "☁️ Salvato su Google Drive\n📎 [Apri link]({link})",
        "no_drive": "💾 Video inviato direttamente (Google Drive non configurato)",

        # Errors
        "error": "❌ Generazione fallita\n\nMotivo: `{error}`\n\nRiprova o cambia modello.",
        "error_model_timeout": "⏰ Il modello non risponde, riprova più tardi.",
        "error_api": "🔌 Errore API: `{error}`",
        "error_no_permission": "🚫 Non hai i permessi per usare questo bot.",
        "error_invalid_url": "❌ URL non valido. Invia un link prodotto valido.",
        "error_image_too_large": "❌ Immagine troppo grande (max 20MB). Comprimi e riprova.",
        "error_ffmpeg": "❌ Elaborazione video fallita: `{error}`",
        "error_drive_upload": "⚠️ Caricamento Drive fallito, invio diretto del video.",

        # Cancellation
        "cancel": "Operazione annullata. Invia /start per ricominciare.",
        "confirm_cancel": "Confermi l'annullamento della generazione video?",
        "btn_confirm": "✅ Sì, annulla",
        "btn_back": "↩️ Torna indietro",

        # Summary
        "generation_summary": (
            "📋 *Riepilogo Generazione*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎭 Modalità: `{mode}`\n"
            "🤖 Modello: `{model}`\n"
            "⏱ Durata: `{duration}` secondi\n"
            "🎞 Clip: `{segments}`\n"
            "🌍 Lingua: `{language}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Confermi e avvii la generazione?"
        ),
        "btn_generate": "🎬 Genera Video",
        "btn_cancel": "❌ Annulla",

        # Misc
        "unknown_command": "Comando sconosciuto. Invia /start per iniziare.",
        "busy": "⚙️ Elaborando la richiesta precedente, attendere...",
        "frame_chaining_notice": "🔗 Frame chaining attivo per transizioni fluide tra le scene",
    },
}

# ─────────────────────────────────────────────────────────────
# Human-readable display names for models, modes, languages
# ─────────────────────────────────────────────────────────────

MODEL_DISPLAY_NAMES = {
    "sora_2": "Sora 2",
    "sora_2_pro": "Sora 2 Pro",
    "seedance_2": "Seedance 2.0",
    "veo_3": "Veo 3.0",
    "veo_3_pro": "Veo 3.0 Pro",
    "veo_31_pro": "Veo 3.1 Pro",
}

MODE_DISPLAY_NAMES = {
    "zh": {
        "text_to_video": "文字转视频",
        "image_to_video": "图片转视频",
        "url_to_video": "URL参考转视频",
    },
    "en": {
        "text_to_video": "Text to Video",
        "image_to_video": "Image to Video",
        "url_to_video": "URL to Video",
    },
    "it": {
        "text_to_video": "Testo a Video",
        "image_to_video": "Immagine a Video",
        "url_to_video": "URL a Video",
    },
}

LANGUAGE_DISPLAY_NAMES = {
    "zh": {"zh": "中文", "en": "Chinese", "it": "Cinese"},
    "en": {"zh": "英语", "en": "English", "it": "Inglese"},
    "it": {"zh": "意大利语", "en": "Italian", "it": "Italiano"},
}


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def get_message(key: str, lang: str = "zh", **kwargs: Any) -> str:
    """Retrieve a localized message, falling back to English then key.
    
    Args:
        key: Message key from MESSAGES dict
        lang: Language code ('zh', 'en', 'it')
        **kwargs: Format arguments for the message template
    
    Returns:
        Formatted, localized message string
    
    Example:
        >>> get_message("complete", lang="en", model="Veo 3.1 Pro",
        ...             duration=30, segments=4, elapsed="2m 30s", filename="video.mp4")
    """
    # Fallback chain: requested lang -> English -> key itself
    msg_dict = MESSAGES.get(lang) or MESSAGES.get("en", {})
    template = msg_dict.get(key) or MESSAGES.get("en", {}).get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            # Return unformatted if format args are missing
            return template
    return template


def get_mode_name(mode: str, lang: str = "zh") -> str:
    """Get human-readable mode name in specified language."""
    return MODE_DISPLAY_NAMES.get(lang, MODE_DISPLAY_NAMES["en"]).get(mode, mode)


def get_model_name(model: str) -> str:
    """Get human-readable model name."""
    return MODEL_DISPLAY_NAMES.get(model, model)


def get_lang_name(language: str, display_lang: str = "zh") -> str:
    """Get language display name.
    
    Args:
        language: The language to get the name of ('zh', 'en', 'it')
        display_lang: The language to display the name in
    """
    return LANGUAGE_DISPLAY_NAMES.get(language, {}).get(display_lang, language)
