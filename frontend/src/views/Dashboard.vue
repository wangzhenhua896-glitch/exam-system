<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>我的考试</span>
              <el-icon><Document /></el-icon>
            </div>
          </template>
          <div class="stat-number">{{ stats.myExams }}</div>
          <div class="stat-label">已参加考试</div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>平均分</span>
              <el-icon><TrendCharts /></el-icon>
            </div>
          </template>
          <div class="stat-number">{{ stats.averageScore }}</div>
          <div class="stat-label">历史平均分</div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>及格率</span>
              <el-icon><CircleCheck /></el-icon>
            </div>
          </template>
          <div class="stat-number">{{ stats.passRate }}%</div>
          <div class="stat-label">考试及格率</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card class="recent-exams">
      <template #header>
        <div class="card-header">
          <span>最近考试</span>
          <el-button type="primary" text @click="$router.push('/exams')">
            查看全部
          </el-button>
        </div>
      </template>
      
      <el-table :data="recentExams" style="width: 100%">
        <el-table-column prop="title" label="考试名称" />
        <el-table-column prop="start_time" label="开始时间">
          <template #default="{ row }">
            {{ formatDate(row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration_minutes" label="时长">
          <template #default="{ row }">
            {{ row.duration_minutes }} 分钟
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="startExam(row.id)">
              参加考试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty v-if="recentExams.length === 0" description="暂无考试" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { examApi, submissionApi } from '@/api'

const router = useRouter()

const stats = ref({
  myExams: 0,
  averageScore: 0,
  passRate: 0
})

const recentExams = ref([])

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const startExam = async (examId) => {
  try {
    await submissionApi.startExam(examId)
    router.push(`/exams/${examId}/take`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '开始考试失败')
  }
}

const loadData = async () => {
  try {
    // 加载考试列表
    const exams = await examApi.getList()
    recentExams.value = exams.slice(0, 5)
    
    // 加载答题记录
    const submissions = await submissionApi.getMyList()
    stats.value.myExams = submissions.length
    
    if (submissions.length > 0) {
      const totalScore = submissions.reduce((sum, s) => sum + s.total_score, 0)
      const maxScore = submissions.reduce((sum, s) => sum + s.max_score, 0)
      stats.value.averageScore = maxScore > 0 
        ? Math.round((totalScore / maxScore) * 100) 
        : 0
      
      const passed = submissions.filter(s => 
        s.max_score > 0 && (s.total_score / s.max_score) >= 0.6
      ).length
      stats.value.passRate = Math.round((passed / submissions.length) * 100)
    }
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stat-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-number {
  font-size: 36px;
  font-weight: bold;
  color: #409EFF;
  text-align: center;
}

.stat-label {
  text-align: center;
  color: #909399;
  margin-top: 8px;
}

.recent-exams {
  margin-top: 20px;
}
</style>
