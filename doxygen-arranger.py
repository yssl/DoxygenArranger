import csv, copy, subprocess, os, operator, glob, re
from operator import itemgetter

##################################################################
# USER INPUT
##################################################################

# Mandatory doxygen commands you want, which should exist for each symbol.
mandatoryCmds = ['brief','since_tizen']

# Mandatory doxygen commands for one-line doxygen comments beginning with ///<
mandatoryCmdsOneLine = ['since_tizen']

# All doxygen commands you are using across the whole project.
# Each doxygen comment block will be rearranged according to the order of commands in this variable.
# Currently, this ordering is only supported for multi-line doxygen comments, not one-line comments
allCmdsOrder = ['platform','deprecated','brief','details','since_tizen','privlevel','privilege'
            ,'remarks','param','return','retval','exception','pre','post','note','see']

# If DoxygenArranger.py finds following commands, it skips processing that symbol.
noProcessCmds = ['copydoc','addtogroup']


# If any of mandatory commands is absent, insert specified string at that position.
# @brief is a special case. If 'brief' is in the mandatoryCmds var, 
# DoxygenArranger.py first trys to attach @brief in front of 'uncommanded' text that appears first in a doxygen comment block.
# If any other doxygen comment first appears in the comment block, then DoxygenArranger.py inserts insertsIfMandatoryCmdAbsent['brief']
# at the location according to the order in allCmdsOrder var.
insertsIfMandatoryCmdAbsent = {'brief':'@brief DOXY_TODO',
                                'since_tizen':'@since_tizen 2.4'}

# If any symbol does not have a doxygen comment block, value of this var is inserted above the symbol.
# If the value is None, nothing will be inserted.
#insertsIfNoDoxyComment = '// DOXY_TODO'
insertsIfNoDoxyComment = None

# multiSentenceBriefOption's available options are:
#
# 'break' - All @briefs having multi-sentence descriptions are splitted into
# (first sentence) (blank line) (the other sentences)
# If the first paragraph of a doxygen description does not have any doxygen commands,
# DoxygenArranger.py assumes that it means a @brief section and split the paragraph in the above way.
#
# 'print' - Print out information of symbols having multi-sentence @brief descriptions
#
# None - Do nothing.
multiSentenceBriefOption = None
#multiSentenceBriefOption = 'break'
#multiSentenceBriefOption = 'print'

# list of root directories of target source code files
sourceDirs = [
                ]

# target source code file patterns in the root directory
targetFilePatterns = ['*/public-api/*.h', '*/key-grab.h']
#targetFilePatterns = ['*/public-api/*/actor.h']
#targetFilePatterns = ['*/public-api/*/accessibility-manager.h']
#targetFilePatterns = ['*/public-api/enums.h']


# target symbol types

# --c++-kinds options (run ctags --list-kinds)
# C++
    #c  classes
    #d  macro definitions
    #e  enumerators (values inside an enumeration)
    #f  function definitions
    #g  enumeration names
    #l  local variables [off]
    #m  class, struct, and union members
    #n  namespaces
    #p  function prototypes [off]
    #s  structure names
    #t  typedefs
    #u  union names
    #v  variable definitions
    #x  external and forward variable declarations [off]

#targetSymbolTypes = ['p','f']
#targetSymbolTypes = ['c','d','g','n','s','t','u']
#targetSymbolTypes = ['p','f','c','d','g','n','s','t','u']
targetSymbolTypes = ['p','f','c','d','g','n','s','t','u','e']

#targetSymbolTypes = ['c']
#targetSymbolTypes = ['d']
##targetSymbolTypes = ['e']
#targetSymbolTypes = ['g']
##targetSymbolTypes = ['m']
#targetSymbolTypes = ['n']
#targetSymbolTypes = ['s']
#targetSymbolTypes = ['t']
#targetSymbolTypes = ['u']
##targetSymbolTypes = ['v']


##################################################################
# SCRIPT ROUTINE
##################################################################

#################################
# functions
def getSymbolLineNums(headerPath):
    symbolLineNums = []

    proc = subprocess.Popen(['ctags --c++-kinds=+p -f - --fields=+n %s'%headerPath], stdout=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    #print out
    tag_list = out.split('\n')

    for rawTagLine in tag_list:
        line = rawTagLine
        #print rawTagLine
        if len(line)==0 or line[0]=='!':
            continue

        code_start = line.find('/^')
        code_end = line.find('$/;"')
        if code_start==-1 or code_end==-1:
            #print 'ERROR code_start'
            #print rawTagLine
            ##exit()
            #continue
            tokens = line.split()
            del tokens[2]
            line = ' '.join(tokens)
        else:
            #code = line[code_start+2:code_end].strip()
            line = line[:code_start] + line[code_end+4:]

        #print code
        #print line

        path_start = line.find(headerPath)
        if path_start==-1:
            print 'ERROR path_start'
            print rawTagLine
            exit()

        symbol = line[:path_start-1].strip()
        #print symbol

        line2 = line[path_start-1:]
        tokens = line2.split()
        #print tokens

        headerPath = tokens[0]
        typeStr = tokens[1]
        lineStr = tokens[2]

        #print headerPath
        #print typeStr
        #print lineStr
        #print

        if len(lineStr.split(':')) < 2:
            print 'ERROR line num does not exist'
            print rawTagLine
            exit()

        lineNum = int(lineStr.split(':')[1])

        #if len(tokens)<4:
            #print 'ERROR class or namespace does not exist'
            #print rawTagLine
            #exit()

        #clsNspName = tokens[3]
        ##print clsNspName

        symbolLineNums.append([lineNum, typeStr, line.replace('\t','  ')])

    symbolLineNums.sort(key=itemgetter(0))
    return symbolLineNums


def getDoxyCommentRanges(codeLines, headerPath):
    symLineNums = getSymbolLineNums(headerPath)

    #for lineNum in symLineNums:
        #print lineNum

    doxyRanges = []
    for i in range(len(symLineNums)):
        lineNum = symLineNums[i][0]
        typeStr = symLineNums[i][1]
        if typeStr in targetSymbolTypes:
            startLine = symLineNums[i-1][0]+1 if i>0 else 1
            endLine = lineNum
            doxyRanges.append([-1,-1, 'multi-line', symLineNums[i][2]])
            for l in range(startLine, endLine+1):

                # JavaDoc or Qt style
                if '/**' == codeLines[l-1].lstrip()[:3] or '/*!' == codeLines[l-1].lstrip()[:3]:
                    doxyRanges[-1][0] = l+1
                elif '*/' == codeLines[l-1].lstrip()[:2] and doxyRanges[-1][0]!=-1:
                    doxyRanges[-1][1] = l-1

                # multiline c++ style
                if '///' == codeLines[l-1].lstrip()[:3] or '//!' == codeLines[l-1].lstrip()[:3]:
                    if doxyRanges[-1][0]==-1:
                        doxyRanges[-1][0] = l
                    else:
                        doxyRanges[-1][1] = l

            # one-line comment
            if '///<' in codeLines[endLine-1]:
                doxyRanges[-1][2] = 'one-line'
                doxyRanges[-1][0] = endLine
                doxyRanges[-1][1] = endLine
            else:
                if doxyRanges[-1][0]==-1 and doxyRanges[-1][1]==-1:
                    doxyRanges[-1][2] = 'no-comment'
                    doxyRanges[-1][0] = endLine
                    doxyRanges[-1][1] = endLine
                elif doxyRanges[-1][0] > doxyRanges[-1][1]:
                    doxyRanges[-1][2] = 'no-contents'
                    doxyRanges[-1][0] = endLine
                    doxyRanges[-1][1] = endLine

    #print
    #for r in doxyRanges:
        #print r

    return doxyRanges

def isInDoxyCmdGroup(aWord, doxyCmdGroup):
    if len(aWord)>1 and (aWord[0]=='@' or aWord[0]=='\\') and aWord[1:] in doxyCmdGroup:
        return True
    else:
        return False

def getDoxyCmdInLine(allCmds, line):
    for cmd in allCmds:
        if '@'+cmd in line: 
            return '@'+cmd
        elif '\\'+cmd in line:
            return '\\'+cmd
    return None

gDoxyCmdPrefix = '@'

def getReformattedDoxyCommentOneLine(oneCodeLine, lineNum, headerPath, funcInfo):
    # temp - to remove property name
    #tokens = oneCodeLine.split()
    ##print tokens
    #for i in range(len(tokens)):
    #    if i>0 and i<len(tokens)-1 and tokens[i]=='name' and tokens[i-1]=='///<':
    #        #print oneCodeLine
    #        oneCodeLine = oneCodeLine.replace(tokens[i],'',1)
    #        oneCodeLine = oneCodeLine.replace(tokens[i+1],'',1)
    #        pos = oneCodeLine.find('///<')
    #        oneCodeLine = oneCodeLine[:pos] + '///< ' + oneCodeLine[pos+4:].lstrip()
    #        #print oneCodeLine
    #        #print
    #        break

    for mandatoryCmd in mandatoryCmdsOneLine:
        if mandatoryCmd not in oneCodeLine:
            oneCodeLine += ' '+insertsIfMandatoryCmdAbsent[mandatoryCmd]
    return oneCodeLine

def getReformattedDoxyCommentLines(doxyCommentLines, lineNum, headerPath, funcInfo):
    global gDoxyCmdPrefix

    #print '===='
    #print doxyCommentLines

    ##################################
    # analyzing
    reformattedLines = []
    startPos = -1
    cmdStartPos = -1
    baseLine_i = 0
    for i in range(len(doxyCommentLines)):
        line = doxyCommentLines[i]
        cmdInLine = getDoxyCmdInLine(allCmdsOrder, line)
        if cmdInLine!=None:
            if gDoxyCmdPrefix=='':
                gDoxyCmdPrefix = cmdInLine[0]
            cmdStartPos = line.find(cmdInLine)
            baseLine_i = i
            break

    if cmdStartPos==-1:
        for i in range(len(doxyCommentLines)):
            line = doxyCommentLines[i]
            tokens = line.split()
            if len(tokens) > 1:
                cmdStartPos = line.find(tokens[1])
                baseLine_i = i
                break

    if cmdStartPos==-1:
        print 'ERROR cmdStartPos'
        for line in doxyCommentLines:
            print line
        exit()

    prefix = doxyCommentLines[baseLine_i][:cmdStartPos]
    #print doxyCommentLines[baseLine_i]
    #print prefix

    cmdGroups = {}
    latestCmd = ''
    for line in doxyCommentLines:
        if prefix in line:
            realLine = line.replace(prefix,'',1)
        else:
            realLine = line.replace(prefix[:-1],'',1)

        realTokens = re.split(' |\[', realLine)

        #print '----'
        #print realLine
        #print realTokens

        if len(realTokens)>0:

            # temp - to remove markdown table
            #if len(realTokens[0]) > 0 and \
            #    realTokens[0][0] == '|' or \
            #    ( len(realTokens)==1 and ( realTokens[0]=='Signals' or realTokens[0]=='Actions' ) ):
            #    continue

            if realTokens[0] not in cmdGroups:
                if isInDoxyCmdGroup(realTokens[0], noProcessCmds):
                    return doxyCommentLines
                elif isInDoxyCmdGroup(realTokens[0], allCmdsOrder):
                    cmdGroups[realTokens[0]] = [realLine]
                    latestCmd = realTokens[0]
                else:
                    if latestCmd=='':
                        print 'WARNING on %s'%funcInfo
                        print '(at line %d of original %s)'%(lineNum, headerPath)
                        print ': No doxygen tag at the beginning.'
                        print
                        latestCmd = 'no_brief_at_beginning'
                        cmdGroups[latestCmd] = [realLine]
                    else:
                        cmdGroups[latestCmd].append(realLine)
            else:
                cmdGroups[realTokens[0]].append(realLine)
        else:
            cmdGroups[latestCmd].append(realLine)

        #print cmdGroups
        #print

    #print '----groups'
    #print cmdGroups
    #print

    ##################################
    # multiSentenceBriefOption check
    if multiSentenceBriefOption != None:
        isMultiBrief = False
        for cmd in cmdGroups:
            if cmd == gDoxyCmdPrefix+'brief' or cmd == 'no_brief_at_beginning':
                numDots = 0
                for bline in cmdGroups[cmd]:
                    if bline=='':
                        break
                    elif '.' in bline:
                        numDots += 1
                if numDots > 1:
                    isMultiBrief = True

                if isMultiBrief:
                    if multiSentenceBriefOption == 'break':
                        blines = cmdGroups[cmd]
                        newBLines = []
                        alreadyBreaked = False
                        for i in range(len(blines)):
                            bline = blines[i]
                            posDot = bline.find('.')
                            if alreadyBreaked==False:
                                if posDot > -1:
                                    newBLines.append(bline[:posDot+1])
                                    newBLines.append('')
                                    if len(bline) > posDot+1:
                                        newBLines.append(bline[posDot+1:].lstrip())
                                    alreadyBreaked = True
                                else:
                                    newBLines.append(bline)
                            else:
                                newBLines.append(bline)

                        cmdGroups[cmd] = newBLines
                        #print newBLines

                        print 'WARNING on %s'%funcInfo
                        print '(at line %d of original %s)'%(lineNum, headerPath)
                        print ':Multi-sentence @brief description. Break it.'
                        print

                    elif multiSentenceBriefOption == 'print':
                        print 'ERROR on %s'%funcInfo
                        print '(at line %d of original %s)'%(lineNum, headerPath)
                        print ':Multi-sentence @brief description.'
                        print
                break

    ##################################
    # reformatting
    newDoxyLines = []
    copyCmdGroups = copy.deepcopy(cmdGroups)

    #print
    #print '-----------'
    #print cmdGroups

    for cmd in allCmdsOrder:
        cmdExists = False
        for realCmd in cmdGroups:
            if gDoxyCmdPrefix+cmd in realCmd:
                for line in cmdGroups[realCmd]:
                    newLine = prefix + line
                    newLine = newLine.rstrip()
                    newDoxyLines.append(newLine)
                del copyCmdGroups[realCmd]
                cmdExists = True

                #print cmd, realCmd, gDoxyCmdPrefix+cmd
                #print '-----------break'

                break

        if cmdExists==False and cmd in mandatoryCmds:
            #if True:
            if cmd!='since_tizen':
                print 'WARNING on %s'%funcInfo
                print '(at line %d of original %s)'%(lineNum, headerPath)
                print ':Doxygen cmd \"%s\" does not exist. Inserting %s'%(cmd, repr(insertsIfMandatoryCmdAbsent[cmd]))
                print

            if cmd=='brief' and 'no_brief_at_beginning' in cmdGroups:
                for i in range(len(cmdGroups['no_brief_at_beginning'])):
                    line = cmdGroups['no_brief_at_beginning'][i]
                    if i==0:
                        newLine = prefix + gDoxyCmdPrefix+'brief ' + line
                    else:
                        newLine = prefix + line
                    newLine = newLine.rstrip()
                    newDoxyLines.append(newLine)
                del copyCmdGroups['no_brief_at_beginning']
            else:
                newLine = prefix + insertsIfMandatoryCmdAbsent[cmd]
                newLine = newLine.rstrip()
                newDoxyLines.append(newLine)

    if len(cmdGroups)>0:
        for uncmd in copyCmdGroups:
            for line in copyCmdGroups[uncmd]:
                print 'WARNING on %s'%funcInfo
                print '(at line %d of original %s)'%(lineNum, headerPath)
                print ':Unexpected doxygen command (not defined in var allCmdsOrder): %s'%uncmd
                print
                newLine = prefix + line
                newLine = newLine.rstrip()
                newDoxyLines.append(newLine)

    #print '----newDoxyLines'
    #print newDoxyLines

    return newDoxyLines

#################################
# get target file list
findopt = ''
for i in range(len(targetFilePatterns)):
    pattern = targetFilePatterns[i]
    findopt += '-ipath \''+pattern+'\' -print'
    if i < len(targetFilePatterns)-1:
        findopt += ' -o '

headerList = []
for sourceDir in sourceDirs:
    proc = subprocess.Popen(['find '+sourceDir+' '+findopt], stdout=subprocess.PIPE, shell=True)
    #print 'find '+sourceDir+' '+findopt
    (out, err) = proc.communicate()
    out = out.strip()
    if len(out) > 0:
        headerList.extend(out.split('\n'))
#print headerList

#################################
# open & modify file
for headerPath in headerList:
    #print headerPath

    with open(headerPath, 'r') as f:
        code = f.read()
        codeLines = code.split('\n')

    doxyCommentRanges = getDoxyCommentRanges(codeLines, headerPath)

    outCodeLines = []
    doxyComment = ''

    i = 0
    while i < len(codeLines):
        lineNum = i+1
        lineStr = codeLines[i]

        if len(doxyCommentRanges)>0:
            startLine = doxyCommentRanges[0][0]
            endLine = doxyCommentRanges[0][1]
            ret = doxyCommentRanges[0][2]
            funcInfo = doxyCommentRanges[0][3]

            if lineNum==startLine:

                #print '--------'
                #print lineStr
                #print funcInfo
                #print lineNum
                #print doxyCommentRanges[0]

                if ret=='multi-line':
                    outCodeLines.extend(getReformattedDoxyCommentLines(codeLines[startLine-1:endLine], lineNum, headerPath, funcInfo))
                    i += endLine-startLine
                elif ret=='one-line':
                    outCodeLines.append(getReformattedDoxyCommentOneLine(codeLines[startLine-1], lineNum, headerPath, funcInfo))
                elif ret=='no-comment':
                    print 'WARNING on %s'%funcInfo
                    print '(at line %d of original %s)'%(lineNum, headerPath)
                    print ': No doxygen comments at all.'
                    print
                    if insertsIfNoDoxyComment!=None:
                        outCodeLines.append(insertsIfNoDoxyComment+' - no comments')
                    outCodeLines.append(lineStr)
                elif ret=='no-contents':
                    print 'WARNING on %s'%funcInfo
                    print '(at line %d of original %s)'%(lineNum, headerPath)
                    print ': Doxygen comments exists, but no contents.'
                    print
                    if insertsIfNoDoxyComment!=None:
                        outCodeLines.append(insertsIfNoDoxyComment+' - no contents')
                    outCodeLines.append(lineStr)
                else:
                    print 'WARNING on %s'%funcInfo
                    print '(at line %d of original %s)'%(lineNum, headerPath)
                    print ': UNEXPECTED CASE'
                    print
                    if insertsIfNoDoxyComment!=None:
                        outCodeLines.append(insertsIfNoDoxyComment+' - unexpected')
                    outCodeLines.append(lineStr)

                doxyCommentRanges.pop(0)
            else:
                outCodeLines.append(lineStr)
        else:
            outCodeLines.append(lineStr)

        i += 1

    with open(headerPath, 'w') as f:
        f.write('\n'.join(outCodeLines))
