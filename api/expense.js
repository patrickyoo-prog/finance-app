export default async function handler(req, res) {
  // CORS 헤더 설정
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { date, amount, category, type, memo, createdAt } = req.body;

  if (!date || !amount || !category || !type) {
    return res.status(400).json({
      error: '필수 항목을 모두 입력하세요',
      required: ['date', 'amount', 'category', 'type']
    });
  }

  const notionToken = process.env.NOTION_API_TOKEN;
  const databaseId = process.env.NOTION_DATABASE_ID;

  if (!notionToken || !databaseId) {
    console.error('Missing environment variables');
    return res.status(500).json({
      error: '서버 설정 오류',
      details: 'Notion API 설정이 필요합니다'
    });
  }

  try {
    const notionResponse = await fetch('https://api.notion.com/v1/pages', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${notionToken}`,
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28',
      },
      body: JSON.stringify({
        parent: {
          database_id: databaseId.replace(/-/g, ''),
        },
        properties: {
          거래내용: {
            title: [
              {
                text: {
                  content: `${category} - ₩${parseInt(amount).toLocaleString('ko-KR')}`,
                },
              },
            ],
          },
          Date: {
            date: {
              start: date,
            },
          },
          Amount: {
            number: parseInt(amount),
          },
          Category: {
            select: {
              name: category,
            },
          },
          Type: {
            select: {
              name: type,
            },
          },
          Memo: {
            rich_text: [
              {
                text: {
                  content: memo || '',
                },
              },
            ],
          },
        },
      }),
    });

    const notionData = await notionResponse.json();

    if (!notionResponse.ok) {
      console.error('Notion API Error:', {
        status: notionResponse.status,
        error: notionData.error,
        message: notionData.message,
      });

      let errorMessage = 'Notion 저장 실패';
      if (notionData.message) {
        errorMessage = notionData.message;
      }

      return res.status(notionResponse.status).json({
        error: errorMessage,
        details: notionData,
      });
    }

    return res.status(201).json({
      success: true,
      message: '✅ 가계부에 저장되었습니다',
      pageId: notionData.id,
    });

  } catch (error) {
    console.error('API Handler Error:', error);
    return res.status(500).json({
      error: '서버 오류 발생',
      details: error.message,
    });
  }
}
