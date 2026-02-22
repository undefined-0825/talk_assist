import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart'; // ★ クリップボード用
import 'package:http/http.dart' as http;
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

void main() {
  runApp(const MyApp());
}

/// アプリ全体
class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'トークアシスト',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String _text = '';
  String _summary = '';
  List<String> _replies = [];
  bool _loading = false;
  String? _error;

  String _tone = 'standard'; // 'standard' | 'night' | 'business'

  // ★ サーバ側の長文対策と緩く合わせる（警告用）
  static const int _maxCharsHint = 8000;

  // ★ 共有テキストを反映するためのコントローラ
  final TextEditingController _textController = TextEditingController();

  @override
  void initState() {
    super.initState();

    // アプリ起動中に共有された場合
    ReceiveSharingIntent.getTextStream().listen(
      (String? value) {
        if (value != null && value.isNotEmpty) {
          setState(() {
            _text = value;
            _textController.text = value;
          });
        }
      },
      onError: (err) {
        // ログ取りたければここで print(err);
      },
    );

    // アプリが完全終了状態から共有で起動した場合
    ReceiveSharingIntent.getInitialText().then((String? value) {
      if (value != null && value.isNotEmpty) {
        setState(() {
          _text = value;
          _textController.text = value;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final hasResult = _summary.isNotEmpty || _replies.isNotEmpty;
    final textLen = _text.length;
    final isTooLong = textLen > _maxCharsHint;

    return Scaffold(
      appBar: AppBar(title: const Text('トークアシスト（AI連携）')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ★ トーン選択
              Row(
                children: [
                  const Text('トーン: '),
                  const SizedBox(width: 8),
                  DropdownButton<String>(
                    value: _tone,
                    items: const [
                      DropdownMenuItem(value: 'standard', child: Text('標準')),
                      DropdownMenuItem(value: 'night', child: Text('夜職')),
                      DropdownMenuItem(value: 'business', child: Text('ビジネス')),
                    ],
                    onChanged: (v) {
                      if (v == null) return;
                      setState(() {
                        _tone = v;
                      });
                    },
                  ),
                ],
              ),
              const SizedBox(height: 8),

              const Text(
                'トーク内容をここに貼り付け：',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),

              // 入力エリア（固定高さ）
              SizedBox(
                height: 200,
                child: TextField(
                  controller: _textController,
                  maxLines: null,
                  minLines: null,
                  expands: true,
                  keyboardType: TextInputType.multiline,
                  textInputAction: TextInputAction.newline,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    hintText: 'LINE のトークをコピペして貼り付け',
                  ),
                  onChanged: (v) => setState(() => _text = v),
                ),
              ),

              // ★ 文字数カウンタ
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  '文字数: $textLen / $_maxCharsHint',
                  style: TextStyle(
                    fontSize: 12,
                    color: isTooLong ? Colors.red : Colors.grey,
                  ),
                ),
              ),
              if (isTooLong)
                const Align(
                  alignment: Alignment.centerRight,
                  child: Text(
                    '※ 長すぎる場合は一部だけ使われることがあります',
                    style: TextStyle(fontSize: 11, color: Colors.red),
                  ),
                ),

              const SizedBox(height: 16),

              SizedBox(
                height: 48,
                child: ElevatedButton(
                  onPressed: _text.trim().isEmpty || _loading
                      ? null
                      : () => _runAi(),
                  child: _loading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('要約＆返信案を生成'),
                ),
              ),

              // エラー表示
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(
                  _error!,
                  style: const TextStyle(color: Colors.red, fontSize: 12),
                ),
              ],

              const SizedBox(height: 16),

              // 結果表示エリア（スクロール）
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (_summary.isNotEmpty) ...[
                        const Divider(),
                        const Text(
                          '要約：',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(_summary),
                        const SizedBox(height: 16),
                      ],
                      if (_replies.isNotEmpty) ...[
                        const Text(
                          '返信案：',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        ..._replies.map(
                          (r) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: OutlinedButton(
                              // タップでコピー
                              onPressed: () => _copyReply(r),
                              child: Align(
                                alignment: Alignment.centerLeft,
                                child: Text(r),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// バックエンドのAIエンドポイントを呼び出す
  Future<void> _runAi() async {
    final text = _text.trim();
    if (text.isEmpty) return;

    setState(() {
      _loading = true;
      _error = null;
      _summary = '';
      _replies = [];
    });

    try {
      final uri = Uri.parse('http://localhost:8000/api/talk/assist');
      // 実機用: adb reverse tcp:8000 tcp:8000
      // エミュレータ用に切り替える場合は下記:
      // final uri = Uri.parse('http://10.0.2.2:8000/api/talk/assist');

      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(<String, dynamic>{'text': text, 'tone': _tone}),
      );

      if (resp.statusCode != 200) {
        throw Exception('statusCode: ${resp.statusCode}');
      }

      final json = jsonDecode(resp.body) as Map<String, dynamic>;

      final summary = (json['summary'] ?? '') as String;
      final repliesDynamic = json['replies'];
      final replies = repliesDynamic is List
          ? repliesDynamic.map((e) => e.toString()).toList()
          : <String>[];

      setState(() {
        _summary = summary;
        _replies = replies;
      });
    } catch (e) {
      setState(() {
        _error = 'AI呼び出しに失敗しました: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  /// 返信案をクリップボードにコピー
  Future<void> _copyReply(String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('返信案をコピーしました'),
        duration: Duration(seconds: 1),
      ),
    );
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }
}
