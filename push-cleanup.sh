#!/bin/bash
# Script to push the cleaned-up history to remote

set -e

echo "🔍 Vérifications pré-push..."
echo ""

# Check 1: No tracked Dockerfile/topology files
TRACKED=$(git ls-files | grep -E "Dockerfile|topology" || true)
if [ -n "$TRACKED" ]; then
    echo "❌ ERREUR: Les fichiers sont toujours trackés:"
    echo "$TRACKED"
    exit 1
fi
echo "✅ Aucun fichier Dockerfile/topology tracké"

# Check 2: Files not in HEAD
if git ls-tree -r HEAD -- Dockerfile src/Dockerfile topology.json topology_template.json 2>/dev/null | grep -q .; then
    echo "❌ ERREUR: Les fichiers sont toujours dans le HEAD"
    exit 1
fi
echo "✅ Aucun fichier Dockerfile/topology dans le HEAD"

# Check 3: .gitignore configured
if ! grep -q "Dockerfile" .gitignore; then
    echo "❌ ERREUR: .gitignore ne contient pas les entrées"
    exit 1
fi
echo "✅ .gitignore correctement configuré"

echo ""
echo "📊 Résumé des changements:"
echo ""
git log --oneline -5
echo ""
echo "Local: $(git rev-list --count main) commits"
echo "Remote: $(git rev-list --count origin/main) commits"
echo ""

echo "⚠️  AVERTISSEMENT: Cette opération va faire un FORCE PUSH"
echo "    - Cela va réécrire l'historique sur GitHub"
echo "    - Les fichiers Dockerfile/topology seront DÉFINITIVEMENT supprimés du remote"
echo "    - Les autres développeurs devront faire git reset --hard origin/main"
echo ""

read -p "Êtes-vous sûr? (oui/non) " -n 3 -r
echo
if [[ ! $REPLY =~ ^[Oo][Uu][Ii]$ ]]; then
    echo "❌ Push annulé"
    exit 1
fi

echo ""
echo "🚀 Push en cours..."
echo ""

# Attempt push with lease (safer than --force)
if git push origin main --force-with-lease; then
    echo ""
    echo "✅ Push réussi!"
    echo ""
    echo "🔍 Vérification sur le remote..."
    
    # Pull to verify
    git fetch origin
    if ! git ls-tree -r origin/main -- Dockerfile src/Dockerfile topology.json 2>/dev/null | grep -q .; then
        echo "✅ Confirmé: Les fichiers ont bien été supprimés du remote"
        echo ""
        echo "✨ Nettoyage terminé avec succès!"
    else
        echo "⚠️  Attention: Les fichiers sont toujours visibles sur le remote"
    fi
else
    echo "❌ Push échoué"
    echo ""
    echo "Causes possibles:"
    echo "  - Credentials manquantes (token/SSH key)"
    echo "  - Permissions insuffisantes"
    echo "  - Connexion réseau"
    echo ""
    echo "Solutions:"
    echo "  1. Via SSH: git remote set-url origin git@github.com:lipnelz/robbi.git"
    echo "  2. Via token: Créer un GitHub token et l'utiliser comme password"
    echo "  3. Consulter: cat /home/lipnel/.copilot/session-state/b5093c40-d2f0-41a7-a722-79c64ddf5d04/files/GIT_CLEANUP_GUIDE.md"
    exit 1
fi
