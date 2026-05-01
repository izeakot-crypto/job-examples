const express = require('express');
const router = express.Router();
const ideasController = require('../controllers/ideasController');
const generateIdeasController = require('../controllers/generateIdeas');

// GET /api/ideas?status=pending
router.get('/', ideasController.getIdeas);

// POST /api/ideas
router.post('/', ideasController.createIdea);

// POST /api/ideas/load-more - MUST be before /:id routes
router.post('/load-more', ideasController.loadMoreIdeas);

// POST /api/ideas/generate - NEW: Generate ideas directly - MUST be before /:id routes
router.post('/generate', generateIdeasController.generateIdeas);

// POST /api/ideas/bulk-save - NEW: Receive ideas from N8n workflow - MUST be before /:id routes
router.post('/bulk-save', generateIdeasController.bulkSaveIdeas);

// GET /api/ideas/:id
router.get('/:id', ideasController.getIdeaById);

// POST /api/ideas/:id/approve
router.post('/:id/approve', ideasController.approveIdea);

// POST /api/ideas/:id/reject
router.post('/:id/reject', ideasController.rejectIdea);

// POST /api/ideas/:id/rewrite — AI-refine idea based on user edits
router.post('/:id/rewrite', ideasController.rewriteIdea);

// DELETE /api/ideas/:id
router.delete('/:id', ideasController.deleteIdea);

module.exports = router;
