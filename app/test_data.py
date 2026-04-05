"""
测试数据集
包含题目、标准答案、学生答案和预期分数
用于验证评分规则的合理性
"""

TEST_DATASET = {
    "name": "简答题评分测试集",
    "description": "用于验证 AI 评分系统合理性的测试数据",
    "subject": "人工智能基础",
    "max_score": 10,
    "items": [
        {
            "id": 1,
            "question": "请简述人工智能的发展历程。",
            "standard_answer": "人工智能起源于 1956 年达特茅斯会议，经历了符号主义、连接主义等发展阶段，近年来随着深度学习和大数据的兴起取得了突破性进展。",
            "student_answers": [
                {
                    "answer": "人工智能起源于 1956 年达特茅斯会议，经历了符号主义、连接主义等发展阶段，近年来随着深度学习和大数据的兴起取得了突破性进展。",
                    "expected_score": 10,
                    "description": "完美答案"
                },
                {
                    "answer": "人工智能起源于 1956 年，经历了几个发展阶段，现在深度学习很流行。",
                    "expected_score": 7,
                    "description": "基本正确但不够详细"
                },
                {
                    "answer": "人工智能就是机器学习，最近几年很火。",
                    "expected_score": 4,
                    "description": "部分正确但过于简单"
                },
                {
                    "answer": "人工智能是一种计算机技术。",
                    "expected_score": 2,
                    "description": "过于笼统"
                },
                {
                    "answer": "人工智能是科幻电影里的概念。",
                    "expected_score": 0,
                    "description": "完全错误"
                }
            ]
        },
        {
            "id": 2,
            "question": "什么是机器学习？请举例说明。",
            "standard_answer": "机器学习是让计算机从数据中自动学习规律的技术。例如垃圾邮件过滤、推荐系统等都是机器学习的典型应用。",
            "student_answers": [
                {
                    "answer": "机器学习是让计算机从数据中自动学习规律的技术。例如垃圾邮件过滤、推荐系统等都是机器学习的典型应用。",
                    "expected_score": 10,
                    "description": "完美答案"
                },
                {
                    "answer": "机器学习是人工智能的一个分支，可以让计算机从数据中学习。比如推荐系统。",
                    "expected_score": 7,
                    "description": "基本正确"
                },
                {
                    "answer": "机器学习就是让电脑变聪明。",
                    "expected_score": 3,
                    "description": "过于简单"
                },
                {
                    "answer": "机器学习是一种算法，用于数据分析。",
                    "expected_score": 5,
                    "description": "部分正确"
                }
            ]
        },
        {
            "id": 3,
            "question": "请解释深度学习与传统机器学习的区别。",
            "standard_answer": "深度学习使用多层神经网络自动学习特征表示，而传统机器学习需要人工设计特征。深度学习在图像识别、语音识别等任务上表现更优。",
            "student_answers": [
                {
                    "answer": "深度学习使用多层神经网络自动学习特征表示，而传统机器学习需要人工设计特征。深度学习在图像识别、语音识别等任务上表现更优。",
                    "expected_score": 10,
                    "description": "完美答案"
                },
                {
                    "answer": "深度学习是机器学习的一种，使用神经网络，不需要人工提取特征。",
                    "expected_score": 7,
                    "description": "基本正确"
                },
                {
                    "answer": "深度学习比机器学习更先进。",
                    "expected_score": 3,
                    "description": "过于简单"
                },
                {
                    "answer": "深度学习就是很多层的神经网络，可以自动学习特征，而传统方法需要手工设计特征。",
                    "expected_score": 8,
                    "description": "良好"
                }
            ]
        },
        {
            "id": 4,
            "question": "什么是神经网络？它的工作原理是什么？",
            "standard_answer": "神经网络是受生物神经系统启发的计算模型，由大量神经元节点组成。通过调整连接权重来学习输入输出之间的映射关系。",
            "student_answers": [
                {
                    "answer": "神经网络是受生物神经系统启发的计算模型，由大量神经元节点组成。通过调整连接权重来学习输入输出之间的映射关系。",
                    "expected_score": 10,
                    "description": "完美答案"
                },
                {
                    "answer": "神经网络模拟人脑，由神经元组成，通过训练调整权重来学习。",
                    "expected_score": 7,
                    "description": "基本正确"
                },
                {
                    "answer": "神经网络就是一种计算机程序。",
                    "expected_score": 2,
                    "description": "过于笼统"
                }
            ]
        },
        {
            "id": 5,
            "question": "请简述自然语言处理的主要应用场景。",
            "standard_answer": "自然语言处理主要应用于机器翻译、情感分析、智能客服、文本摘要等场景，近年来大语言模型取得了显著进展。",
            "student_answers": [
                {
                    "answer": "自然语言处理主要应用于机器翻译、情感分析、智能客服、文本摘要等场景，近年来大语言模型取得了显著进展。",
                    "expected_score": 10,
                    "description": "完美答案"
                },
                {
                    "answer": "自然语言处理用于翻译、聊天机器人等。",
                    "expected_score": 6,
                    "description": "基本正确但不够全面"
                },
                {
                    "answer": "就是让计算机理解人类语言的技术。",
                    "expected_score": 3,
                    "description": "只说了定义没说应用"
                },
                {
                    "answer": "自然语言处理的应用包括机器翻译、情感分析、问答系统、文本生成等。",
                    "expected_score": 8,
                    "description": "良好"
                }
            ]
        }
    ]
}


def get_test_dataset():
    """获取测试数据集"""
    return TEST_DATASET


def get_test_items():
    """获取所有测试项（展开学生答案）"""
    items = []
    for question_item in TEST_DATASET["items"]:
        for student_answer in question_item["student_answers"]:
            items.append({
                "question_id": question_item["id"],
                "question": question_item["question"],
                "standard_answer": question_item["standard_answer"],
                "student_answer": student_answer["answer"],
                "expected_score": student_answer["expected_score"],
                "description": student_answer["description"],
                "max_score": TEST_DATASET["max_score"],
            })
    return items
