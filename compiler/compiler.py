import re
from class_def.function import Function
from class_def.assembly import Assembly
import sys, getopt
from subprocess import call
import os
from class_def.conversions.helpers import subleq
import assembler

def main(argv):
    compilerVersion = 0.11;
    [inputFileName, ext, assemFileName, outputFileName, fVerbose, debugging, cores, language, blLength, zero, noExit] = parseCmdArgs(argv);

    #run clang if given a c or cl file
    if ext == 'c':
        command = "clang -S -emit-llvm -o " + inputFileName + ".ll " + inputFileName;
        call(command.split());
        inputFileName = inputFileName + ".ll"; 

    elif ext == 'cl':
        command = "clang -S -emit-llvm -x cl -o " +  inputFileName + ".ll " + inputFileName;
        call(command.split());
        inputFileName = inputFileName + ".ll";

    #read the file
    inputFile = open(inputFileName,'r');
    inputString = inputFile.read();
    inputFile.close();

    #clean up the .ll file if clang was run
    if ext in ('c', 'cl'):
        os.remove(inputFileName);

    #walk through the input file, parsing each function and creating a function 
    #class for each function
    functions = [];
    
    currentIndex = inputString.find("define", 0);
    while(currentIndex != -1):
        endIndex = inputString.find("}",currentIndex);
        functions.append(Function(inputString[currentIndex:endIndex]));
        currentIndex = inputString.find("define",endIndex);


    #struct containing compiler information
    assem = Assembly(language);

    #walk through each function and generate subleq assembly
    for function in functions:
        #allocate function parameter memory
        function.allocateParamMemory(assem);

        #generate subleq instructions
        for instruction in function.instructions:
            instruction.generateSubleq(instruction,assem);

    #wrap the instructions in the nested for loops for each dimension
    if language == 'cl':
        assem.generateKernelLoop();

    #create fake global id data and jump to location -1 at the end if debugging is on
    if debugging:
        assem.dataMem["work_dims"] = 3
        assem.dataMem["glob_ids0"] = 7390;
        assem.dataMem["glob_ids1"] = 3040;
        assem.dataMem["glob_ids2"] = 3902;
        assem.dataMem["glob_ids3"] = 3902;
        assem.dataMem["glob_ids4"] = 0;
        assem.dataMem["glob_ids5"] = 0;
        assem.dataMem["glob_ids6"] = 0;
        assem.dataMem["glob_ids7"] = 0;
        assem.dataMem["glob_ids8"] = 0;
        assem.dataMem["glob_ids9"] = 0;
        assem.dataMem["glob_ids10"] = 0;
        
        assem.dataMem["glob_ids"] = "&glob_ids0";
        assem.dataMem["glob_idsMax0"] = 7392;
        assem.dataMem["glob_idsMax1"] = 3041;
        assem.dataMem["glob_idsMax2"] = 3903;
        assem.dataMem["glob_idsMax3"] = 3903;
        assem.dataMem["glob_idsMax4"] = 1;
        assem.dataMem["glob_idsMax5"] = 1;
        assem.dataMem["glob_idsMax6"] = 1;
        assem.dataMem["glob_idsMax7"] = 1;
        assem.dataMem["glob_idsMax8"] = 1;
        assem.dataMem["glob_idsMax9"] = 1;
        assem.dataMem["glob_idsMax10"] = 1;
        assem.dataMem["glob_idsMax"] = "&glob_idsMax0";

        if not noExit:
            print "noexit"
            assem.progMem.append(subleq("t0","t0","#-1"));


    output = open(assemFileName,"w");
    output.write("//Compiler with j-backend-" + str(compilerVersion) + "\n");
    if language not in ['cl']:
        cores = 1;

    for i in range(0,cores):
        output.write("\n\n\nPROGRAM_MEM_" + str(i) + ":\n\n");

        filt = re.compile("\s*//.*");
        for line in assem.progMem:

            #filter out comments if debugging flag is set
            if debugging:
                lineToWrite = line;
            else:
                lineToWrite = filt.sub("",line);
            
            if line[-1] != ":":
                lineToWrite += "\n";
                
            output.write(lineToWrite);
            if fVerbose:
                print lineToWrite;


        output.write("\n\n");
        output.write("DATA_MEM_" + str(i) + ":\n\n");
        for mem in assem.dataMem:
            value = assem.dataMem[mem];
            lineToWrite = str(mem) + ":";

            if re.match("-?\d",str(value)):
                lineToWrite += "#";
            lineToWrite += str(value) + "\n";

            output.write(lineToWrite);
            if fVerbose:
                print lineToWrite;

    output.close();

    #run the assembler if necessary
    if outputFileName != "":
        compilerPath = sys.argv[0];
        path = compilerPath[:compilerPath.rindex("compiler.py")];
        command = "python " + path + "assembler.py -i " + assemFileName + " -o " + outputFileName + " -b " + blLength + " " + zero;
        result = call(command.split());
        os.remove(assemFileName);

def parseCmdArgs(argv):
    outputFileName = "";
    fVerbose = False;
    debugging = False;
    frontEnd = False;
    slqOnly = False;
    cores = 2;
    language = 'cl';
    blLength = '0';
    zero = '';
    noExit = False;

#Command line arguments
    try:
        opts, args = getopt.getopt(argv, "i:o:c:vdshl:b:zn")
    except getopt.GetoptError:
        print usage(); 
        sys.exit(2);

    for opt, arg in opts:
        if opt in ("-i", "--infile"):
            inputFileName = arg;

        elif opt in ("-o", "--outfile"):
            outputFileName = arg;
                
        elif opt in ("-v", "--verbose"):
            fVerbose = True;

        elif opt in ("-d", "--debugging"):
            debugging = True;

        elif opt in ("-s", "--subleq"):
            slqOnly = True; #generate subleq assembly only

        elif opt in ("-h", "--help"):
            print usage();
            print getHelp();
            sys.exit(0);

        elif opt in ("-c", "--cores"):
            cores = int(arg);

        elif opt in ("-p", "--print"):
            printOnly = True;
        
        elif opt in ("-l", "--language"):
            language = arg;

        elif opt in ("-b", "--bootloader"):
            blLength = arg;

        elif opt in ("-z", "--zero"):
            zero = "-z";

        elif opt in ("-n", "--noExit"):
            noExit = True;

    if inputFileName == "":
        print usage();
        sys.exit(2);

    if cores < 1:
        print "error - cores must be a positive integer"
        sys.exit(2);

    if language not in languages():
        print "error - not recognized language, acceptable languages are:";
        langs = languages();
        for l in langs:
            print l;
        sys.exit(2);

    extStart = inputFileName.rfind(".");
    if extStart == -1:
        name = inputFileName;
        ext = "";
    else:
        name = inputFileName[:extStart];
        ext = inputFileName[extStart+1:]; 
    assemFileName = name + '.slq';

    if slqOnly:
        outputFileName = "";

    else:
        outputFileName = name + ".machine";

    return inputFileName, ext, assemFileName, outputFileName, fVerbose, debugging, cores, language, blLength, zero, noExit;

def usage():
    return "Usage: python",sys.argv[0],"[-i inputfile] [options]";

def getHelp():

    helpStr = "\
    -i, --infile <inputfile>              specify the input file, [REQUIRED]\n\
    -o, --outputfile <outputfile>         specify the output file, defaults to the input file with .machine as the extension\n\
    -d, --debugging                       don't filterout comments and other debugging stuff like create fake global id data,\n\
    -v, --verbose                         print output to the terminal\n\
    -s, --subleq                          output subleq assembly only, don't convert to machine code\n\
    -c, --cores <cores>                   number of cores that need this program, will create cpu0, cpu1, ... up to cpu{cores-1}\n\
    -l, --language <lang>                 sets the language. Either 'cl' or 'c' \n\
    -b, --bootloader <length>             sets the bootloader length, default 32 (for debugging purposes) \n\
    -z, --zero                            sets unused memory locations to 0\n\
    -n, --noExit                          doesn't append a branch to location -1 at the end\n\
    -h, --help                            display options";

    return helpStr;

def languages():
    return ['c', 'cl'];


if __name__ == '__main__':
    main(sys.argv[1:]);

