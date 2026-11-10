import request from '@/utils/request'

// 区块链存证
export function certBlockchain(data) {
  return request.post('/blockchain/cert', { content: data.content })
}

// 区块链核验
export function verifyBlockchain(hash) {
  return request.post('/blockchain/verify', { hash })
}
