import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'exams',
        name: 'ExamList',
        component: () => import('@/views/exams/ExamList.vue'),
        meta: { title: '考试列表' }
      },
      {
        path: 'exams/:id',
        name: 'ExamDetail',
        component: () => import('@/views/exams/ExamDetail.vue'),
        meta: { title: '考试详情' }
      },
      {
        path: 'exams/:id/take',
        name: 'TakeExam',
        component: () => import('@/views/exams/TakeExam.vue'),
        meta: { title: '参加考试' }
      },
      {
        path: 'my-exams',
        name: 'MyExams',
        component: () => import('@/views/exams/MyExams.vue'),
        meta: { title: '我的考试' }
      },
      {
        path: 'admin/exams',
        name: 'AdminExams',
        component: () => import('@/views/admin/ExamManage.vue'),
        meta: { title: '考试管理', requiresAdmin: true }
      },
      {
        path: 'admin/questions/:examId',
        name: 'AdminQuestions',
        component: () => import('@/views/admin/QuestionManage.vue'),
        meta: { title: '题目管理', requiresAdmin: true }
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/UserManage.vue'),
        meta: { title: '用户管理', requiresAdmin: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // 不需要登录的页面
  if (to.meta.public) {
    next()
    return
  }
  
  // 检查是否登录
  if (!authStore.isAuthenticated) {
    next('/login')
    return
  }
  
  // 检查是否需要管理员权限
  if (to.meta.requiresAdmin && authStore.user?.role !== 'admin' && authStore.user?.role !== 'teacher') {
    next('/dashboard')
    return
  }
  
  next()
})

export default router
