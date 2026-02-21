const fs = require('fs');
const path = require('path');
const https = require('https');

// 配置
const QUIZZES_DIR = path.join(__dirname, 'quizzes');
const QUIZZES_ZH_DIR = path.join(__dirname, 'quizzes_zh');

// 免费翻译 API (MyMemory)
function translate(text) {
    return new Promise((resolve, reject) => {
        const encoded = encodeURIComponent(text);
        const url = `https://api.mymemory.translated.net/get?q=${encoded}&langpair=en|zh-CN`;
        
        https.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    resolve(json.responseData?.translatedText || text);
                } catch(e) {
                    resolve(text);
                }
            });
        }).on('error', () => resolve(text));
    });
}

// 翻译整个 quiz
async function translateQuiz(quizFile) {
    const quizName = path.basename(quizFile);
    console.log(`📝 处理: ${quizName}`);
    
    const content = JSON.parse(fs.readFileSync(quizFile, 'utf8'));
    
    // 翻译 title
    if (content.title) {
        content.title = await translate(content.title);
    }
    
    // 翻译 description
    if (content.description) {
        content.description = await translate(content.description);
    }
    
    // 翻译 questions
    if (content.questions) {
        for (const q of content.questions) {
            if (q.question) {
                q.question = await translate(q.question);
            }
            if (q.options) {
                for (const opt of q.options) {
                    if (opt.text) {
                        opt.text = await translate(opt.text);
                    }
                }
            }
        }
    }
    
    // 翻译 results
    if (content.results) {
        for (const r of content.results) {
            if (r.title) {
                r.title = await translate(r.title);
            }
            if (r.description) {
                r.description = await translate(r.description);
            }
        }
    }
    
    // 写入中文版
    const zhFile = path.join(QUIZZES_ZH_DIR, quizName);
    fs.writeFileSync(zhFile, JSON.stringify(content, null, 2), 'utf8');
    
    console.log(`✅ 已更新: ${quizName}`);
}

// 主逻辑
const args = process.argv.slice(2);

if (args.length > 0) {
    // 翻译指定 quiz
    const quizNum = args[0];
    const quizFile = path.join(QUIZZES_DIR, `quiz_${quizNum}.json`);
    
    if (fs.existsSync(quizFile)) {
        translateQuiz(quizFile);
    } else {
        console.log(`❌ 文件不存在: quiz_${quizNum}.json`);
    }
} else {
    console.log(`
📖 用法:
  node sync_translation.js 1     # 翻译 quiz_1
  node sync_translation.js       # 显示帮助

🔄 监控模式 (需要额外安装 fswatch):
  fswatch -o quizzes/ | while read; do
    node sync_translation.sh $(ls -t quizzes/quiz_*.json | head -1 | sed 's/.*quiz_\\([0-9]*\\).*/\\1/')
  done
`);
}
